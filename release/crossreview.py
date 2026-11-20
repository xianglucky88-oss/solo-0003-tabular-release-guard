from .constraints import narrow
from .model import identifier
from .search import Exhausted, Solver


class UnsupportedMapping(ValueError):
    """The caller-supplied cross-release mapping cannot support a combined check."""


_REF, _CAND = 'reference', 'candidate'


def _ns(side, key):
    return f'{side}.{key}'


def _point(mapping, field, side, known):
    raw = mapping.get(field)
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise UnsupportedMapping(f'mapping field {field} must be a list of cell ids')
    points = []
    for item in raw:
        key = identifier(item)
        if key not in known:
            raise UnsupportedMapping(f'mapping field {field} names unknown {side} cell {key}')
        points.append(key)
    if len(set(points)) != len(points):
        raise UnsupportedMapping(f'mapping field {field} contains duplicates')
    return points


def _resolve(rel_id, raw_key, pool):
    """Resolve one mapping reference to an explicit (side, cell) pair.

    A shared name is ambiguous until the caller qualifies it with the
    'reference.' / 'candidate.' prefix; an unqualified name that exists on
    both sides is rejected so equal names can never silently mean equal scope.
    """
    key = identifier(raw_key)
    if '.' in key:
        prefix, tail = key.split('.', 1)
        if prefix not in pool:
            raise UnsupportedMapping(f'mapping relation {rel_id} uses unknown side prefix {prefix}')
        if tail not in pool[prefix]:
            raise UnsupportedMapping(f'mapping relation {rel_id} names unknown cell {key}')
        return prefix, tail
    owners = [side for side, table_cells in pool.items() if key in table_cells]
    if not owners:
        raise UnsupportedMapping(f'mapping relation {rel_id} names unknown cell {key}')
    if len(owners) > 1:
        raise UnsupportedMapping(
            f'mapping relation {rel_id} must qualify ambiguous same-named cell {key} '
            "with 'reference.' or 'candidate.'")
    return owners[0], key


def _merged_view(reference, candidate, mapping):
    """Build the combined constraint system from two independent tables.

    Cell ids are namespaced per side, so a name shared by both releases never
    implies the same scope: linkage exists only where the caller's qualified
    mapping creates it. All-public mapping relations are checked against
    published values; relations that reach a masked cell enter the combined
    system as asserted linkage, and any later contradiction with public facts
    surfaces as an unsupported mapping.
    """
    if not isinstance(mapping, dict):
        raise UnsupportedMapping('mapping must be a JSON object')
    (ref_table, ref_limit, ref_cells, ref_eqs), (cand_table, cand_limit, cand_cells, cand_eqs) = reference, candidate
    pool = {_REF: ref_cells, _CAND: cand_cells}
    only_ref = _point(mapping, 'only_reference', _REF, ref_cells)
    only_cand = _point(mapping, 'only_candidate', _CAND, cand_cells)
    relations = mapping.get('relations')
    if not isinstance(relations, list) or not relations:
        raise UnsupportedMapping('mapping must carry at least one cross-release relation')

    domains, linear, mapped = {}, [], set()
    seen_ids = set()
    for row in relations:
        if not isinstance(row, dict):
            raise UnsupportedMapping('mapping relation must be an object')
        rel_id = identifier(row['id'])
        if rel_id in seen_ids:
            raise UnsupportedMapping(f'duplicate mapping relation {rel_id}')
        seen_ids.add(rel_id)
        terms = row['terms']
        if not isinstance(terms, list) or not terms or len(terms) != len(set(terms)):
            raise UnsupportedMapping(f'mapping relation {rel_id} has invalid terms')
        resolved = [_resolve(rel_id, row['total'], pool)]
        resolved.extend(_resolve(rel_id, term, pool) for term in terms)
        qualified = [_ns(side, key) for side, key in resolved]
        if len(set(qualified)) != len(qualified) or qualified[0] in qualified[1:]:
            raise UnsupportedMapping(f'mapping relation {rel_id} repeats a cell or totals one of its terms')
        sides = {side for side, _ in resolved}
        if not sides >= {_REF, _CAND}:
            raise UnsupportedMapping(
                f'mapping relation {rel_id} stays inside one release; only cross-release linkage is accepted')

        # Verifiability uses public evidence only. A relation whose cells are
        # all public must balance with the published values. A relation that
        # reaches a masked cell cannot be checked numerically: it enters the
        # merged system as the caller's asserted linkage, and if that linkage
        # contradicts public facts the combined system becomes infeasible and
        # is reported as an unsupported mapping rather than a risk verdict.
        public_values, has_masked = [], False
        for side, key in resolved:
            cell = pool[side][key]
            if cell.mode == 'masked' or cell.count is None:
                has_masked = True
            else:
                public_values.append(cell.count)
        if not has_masked and public_values[0] != sum(public_values[1:]):
            raise UnsupportedMapping(
                f'mapping relation {rel_id} fails the public balance check; same-named cells are not forced equal')
        linear.append({qualified[0]: 1, **{term: -1 for term in qualified[1:]}})
        mapped.update(qualified)

    mapped_ref = {q for q in mapped if q.startswith(_REF + '.')}
    mapped_cand = {q for q in mapped if q.startswith(_CAND + '.')}
    only_ref_q = {_ns(_REF, key) for key in only_ref}
    only_cand_q = {_ns(_CAND, key) for key in only_cand}
    all_ref = {_ns(_REF, key) for key in ref_cells}
    all_cand = {_ns(_CAND, key) for key in cand_cells}
    if only_ref_q & mapped_ref or only_cand_q & mapped_cand:
        raise UnsupportedMapping('a cell cannot be both mapped and listed as version-only')
    if only_ref_q | mapped_ref != all_ref or only_cand_q | mapped_cand != all_cand:
        raise UnsupportedMapping('mapping must classify every cell as either mapped or version-only')

    def add_table(side, limit, cells, equations):
        for key, cell in cells.items():
            qkey = _ns(side, key)
            if cell.mode == 'masked' or cell.count is None:
                domains[qkey] = (0, limit)
            else:
                domains[qkey] = (cell.count, cell.count)
        for eq in equations:
            linear.append({_ns(side, eq.total): 1,
                           **{_ns(side, term): -1 for term in eq.terms}})

    add_table(_REF, ref_limit, ref_cells, ref_eqs)
    add_table(_CAND, cand_limit, cand_cells, cand_eqs)
    return domains, linear


def _extreme(solver, domains, target, find_min):
    """Bisect to the smallest/largest feasible value of target (no private reads)."""
    lo, hi = domains[target]
    while lo < hi:
        mid = (lo + hi) // 2
        if find_min:
            constrained = (lo, mid)
            if solver.feasible({**domains, target: constrained}):
                hi = mid
            else:
                lo = mid + 1
        else:
            constrained = (mid + 1, hi)
            if solver.feasible({**domains, target: constrained}):
                lo = mid + 1
            else:
                hi = mid
    return lo


def cross_review(reference, candidate, mapping, budget):
    """Review a candidate against an already-published public manifest.

    Outcomes per masked cell:
      alternative_exists  - a different feasible value survives the merge;
      uniquely_determined - the combined public constraints pin one value,
                            i.e. disclosure risk is real;
      indeterminate       - the node budget ran out before a conclusion.
    A mapping that public evidence cannot support raises UnsupportedMapping
    instead of producing a verdict.
    """
    if type(budget) is not int or not 1 <= budget <= 5000:
        raise ValueError('node budget must be between 1 and 5000')
    domains, linear = _merged_view(reference, candidate, mapping)
    reduced = narrow(domains, linear)
    if reduced is None:
        raise UnsupportedMapping(
            'the asserted linkage contradicts published values; the cross-release mapping is not supported')
    solver = Solver(linear, budget)
    # Masked status comes from the original domains: narrowing may already pin
    # a cell, and those pinned cells are precisely the risks we must report.
    masked = sorted(key for key, bounds in domains.items() if bounds[0] != bounds[1])
    results = {}
    try:
        for key in masked:
            lowest = _extreme(solver, reduced, key, True)
            highest = _extreme(solver, reduced, key, False)
            results[key] = 'uniquely_determined' if lowest == highest else 'alternative_exists'
    except Exhausted:
        for key in masked:
            results.setdefault(key, 'indeterminate')
    decision = 'allow' if results and all(value == 'alternative_exists' for value in results.values()) else 'hold'
    return {
        'reference_table': reference[0],
        'candidate_table': candidate[0],
        'decision': decision,
        'cells': results,
        'nodes_used': budget - solver.remaining,
    }
