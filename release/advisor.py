"""Masking advice for editors.

The advisor only *recommends* additional masks.  It never rewrites source
counts, never unmasks a cell that is already masked, never changes a structural
zero and never writes a publication.  Every proposed view is checked with the
same ``review`` function that backs ``POST /release/reviews``.

A plan is usable only when the ordinary review says ``allow`` for the proposed
view, which in turn means every masked cell (the original ones plus every newly
masked one) has at least one feasible assignment with a different value.  That
is the check that a newly masked cell is not immediately pinned down by the
remaining relations.
"""

from dataclasses import replace
from itertools import combinations

from .model import identifier
from .review import review


_MAX_PLANS = 40
_MAX_RELAXATIONS = 6


def _id_list(value, field):
    if not isinstance(value, list):
        raise ValueError(f'{field} must be a list of cell identifiers')
    seen = set()
    result = []
    for item in value:
        key = identifier(item)
        if key in seen:
            raise ValueError(f'{field} contains a duplicate cell')
        seen.add(key)
        result.append(key)
    return tuple(result)


def parse_advice(cells, payload):
    """Validate the editor-facing advice request against the table."""
    required = _id_list(payload.get('required_public', []), 'required_public')
    if 'maskable' not in payload:
        raise ValueError('maskable is required (it may be an empty list)')
    maskable = _id_list(payload['maskable'], 'maskable')
    overlap = sorted(set(required) & set(maskable))
    if overlap:
        raise ValueError(f'cells cannot be both required_public and maskable: {overlap}')

    for key in required:
        cell = cells.get(key)
        if cell is None:
            raise ValueError(f'required_public references a missing cell: {key}')
        if cell.mode == 'zero':
            raise ValueError(f'structural zero cannot be made a disclosure choice: {key}')
        if cell.mode != 'public':
            raise ValueError(f'required_public must list currently public cells: {key}')
    for key in maskable:
        cell = cells.get(key)
        if cell is None:
            raise ValueError(f'maskable references a missing cell: {key}')
        if cell.mode == 'zero':
            raise ValueError(f'structural zero is fixed and cannot be masked: {key}')
        if cell.mode != 'public':
            raise ValueError(f'maskable must list currently public cells: {key}')

    raw_values = payload.get('release_values', {})
    if not isinstance(raw_values, dict):
        raise ValueError('release_values must be an object of cell identifiers to integers')
    values = {}
    for key, value in raw_values.items():
        key = identifier(key)
        if key not in cells:
            raise ValueError(f'release_values references a missing cell: {key}')
        if cells[key].mode != 'public':
            raise ValueError(f'release value is only defined for currently public cells: {key}')
        if type(value) is not int or value < 0:
            raise ValueError(f'release value must be a non-negative integer: {key}')
        values[key] = value

    node_budget = payload.get('node_budget', 300)
    if type(node_budget) is not int or not 1 <= node_budget <= 5000:
        raise ValueError('node budget must be between 1 and 5000')
    search_budget = payload.get('search_budget', 512)
    if type(search_budget) is not int or not 1 <= search_budget <= 20000:
        raise ValueError('search budget must be between 1 and 20000')
    target = payload.get('min_release_value')
    if target is not None and (type(target) is not int or target < 0):
        raise ValueError('min_release_value must be a non-negative integer')

    return {
        'required_public': required,
        'maskable': maskable,
        'values': values,
        'node_budget': node_budget,
        'search_budget': search_budget,
        'min_release_value': target,
    }


def _in_relations(key, equations):
    return any(key == equation.total or key in equation.terms for equation in equations)


def _plan(combo, result, values, total_value):
    ordered = tuple(sorted(combo))
    masked_value = sum(values.get(key, 0) for key in ordered)
    return {
        'extra_masked': list(ordered),
        'mask_count': len(ordered),
        'masked_value': masked_value,
        'preserved_value': total_value - masked_value,
        'review': {
            'decision': result['decision'],
            'cells': {key: result['cells'][key] for key in sorted(result['cells'])},
            'newly_masked': {key: result['cells'].get(key) for key in ordered},
            'nodes_used': result['nodes_used'],
        },
    }


def _search(limit, cells, equations, candidates, values, node_budget, search_budget):
    """Enumerate candidate views, best (smallest) subsets first.

    Supersets of a view that already passes review are skipped: they can only
    add masks and can never preserve more release value, so they are dominated
    for both editor objectives.
    """
    total_value = sum(values.get(key, 0) for key, cell in cells.items() if cell.mode == 'public')
    feasible = []
    feasible_sets = []
    unique_sets = []
    layers = []
    evaluated = pruned = inconclusive = nodes = 0
    stopped = False

    for size in range(len(candidates) + 1):
        if stopped:
            break
        layer_complete = True
        layer_definitive = True
        for combo in combinations(candidates, size):
            chosen = frozenset(combo)
            if any(found <= chosen for found in feasible_sets):
                pruned += 1
                continue
            if evaluated >= search_budget:
                stopped = True
                layer_complete = False
                break
            evaluated += 1
            view = {key: replace(cell, mode='masked') if key in chosen else cell
                    for key, cell in cells.items()}
            result = review(limit, view, equations, node_budget)
            nodes += result['nodes_used']
            if any(value == 'indeterminate' for value in result['cells'].values()):
                inconclusive += 1
                layer_definitive = False
                continue
            unique_sets.append({key for key, value in result['cells'].items()
                                if value == 'uniquely_determined'})
            newly_checked = all(result['cells'].get(key) == 'alternative_exists' for key in combo)
            if result['decision'] == 'allow' and newly_checked:
                feasible.append(_plan(combo, result, values, total_value))
                feasible_sets.append(chosen)
        layers.append(layer_complete and layer_definitive)

    complete = not stopped and inconclusive == 0 and len(layers) == len(candidates) + 1
    return {
        'feasible': feasible,
        'unique_sets': unique_sets,
        'layers': layers,
        'evaluated': evaluated,
        'pruned': pruned,
        'inconclusive': inconclusive,
        'nodes': nodes,
        'complete': complete,
        'total_value': total_value,
    }


def _minimum(plans):
    return min(plans, key=lambda plan: (plan['mask_count'], -plan['preserved_value'],
                                        plan['extra_masked']))


def _best(plans):
    return min(plans, key=lambda plan: (-plan['preserved_value'], plan['mask_count'],
                                        plan['extra_masked']))


def _layer_decided(search, size):
    return size < len(search['layers']) and search['layers'][size]


def _relaxations(spec, limit, cells, equations):
    found, unknown = [], []
    keys = spec['required_public']
    if len(keys) > _MAX_RELAXATIONS:
        return {'tested': [], 'enables_plan': [], 'no_plan': [], 'unknown': list(keys),
                'complete': False}
    for key in spec['required_public']:
        maskable = tuple(sorted(set(spec['maskable']) | {key}))
        candidates = tuple(item for item in maskable if _in_relations(item, equations))
        search = _search(limit, cells, equations, candidates, spec['values'],
                         spec['node_budget'], spec['search_budget'])
        if search['feasible']:
            plan = _minimum(search['feasible'])
            found.append({'cell': key, 'status': 'enables_plan',
                          'extra_masked': plan['extra_masked'],
                          'preserved_value': plan['preserved_value']})
        elif search['complete']:
            found.append({'cell': key, 'status': 'no_plan'})
        else:
            unknown.append(key)
    return {
        'tested': list(keys),
        'enables_plan': [item for item in found if item['status'] == 'enables_plan'],
        'no_plan': [item['cell'] for item in found if item['status'] == 'no_plan'],
        'unknown': unknown,
        'complete': not unknown and len(found) == len(keys),
    }


def advise(table, limit, cells, equations, payload):
    spec = parse_advice(cells, payload)
    originals = tuple(sorted(key for key, cell in cells.items() if cell.mode == 'masked'))
    candidates = tuple(sorted(key for key in spec['maskable'] if _in_relations(key, equations)))
    ignored = tuple(sorted(key for key in spec['maskable'] if key not in candidates))
    values = spec['values']
    target = spec['min_release_value']

    search = _search(limit, cells, equations, candidates, values,
                     spec['node_budget'], spec['search_budget'])
    feasible = sorted(search['feasible'],
                      key=lambda plan: (plan['mask_count'], -plan['preserved_value'],
                                        plan['extra_masked']))
    minimum = _minimum(feasible) if feasible else None
    best = _best(feasible) if feasible else None
    candidate_values_zero = all(values.get(key, 0) == 0 for key in candidates)

    minimum_certified = bool(minimum is not None
                             and all(_layer_decided(search, size)
                                     for size in range(minimum['mask_count'])))
    best_certified = bool(
        best is not None
        and (search['complete']
             or candidate_values_zero
             or best['preserved_value'] == search['total_value'])
    )

    if target is None:
        eligible = feasible
    else:
        eligible = [plan for plan in feasible if plan['preserved_value'] >= target]
    recommended = _minimum(eligible) if eligible else None
    recommended_certified = bool(recommended is not None
                                 and all(_layer_decided(search, size)
                                         for size in range(recommended['mask_count'])))

    reason = None
    if search['complete']:
        if not feasible:
            status, reason = 'unsatisfiable', 'no_combination_passes_review'
        elif target is not None and not eligible:
            status, reason = 'unsatisfiable', 'release_value_target_unreachable'
        else:
            status = 'ok'
    else:
        status = 'partial' if recommended is not None else 'incomplete'
        reason = 'review_inconclusive' if search['inconclusive'] else 'search_budget_exhausted'

    detail = None
    relaxations = None
    if status == 'unsatisfiable':
        if reason == 'release_value_target_unreachable':
            detail = {
                'explanation': 'every verified plan preserves less release value than the target',
                'best_achievable_value': best['preserved_value'] if best else None,
            }
        else:
            persistent = None
            counts = {}
            for unique in search['unique_sets']:
                current = {key for key in originals if key in unique}
                for key in current:
                    counts[key] = counts.get(key, 0) + 1
                persistent = current if persistent is None else persistent & current
            relaxations = _relaxations(spec, limit, cells, equations)
            detail = {
                'explanation': ('no subset of the maskable cells yields alternatives for '
                                'every masked cell under the fixed requirements'),
                'persistent_unique': sorted(persistent or ()),
                'unique_in_views': counts,
                'views_checked': len(search['unique_sets']),
                'relaxations': relaxations,
            }

    same_result = None
    if minimum_certified and best_certified:
        same_result = minimum['extra_masked'] == best['extra_masked']

    notes = []
    if ignored:
        notes.append('maskable cells outside every relation were ignored because masking them '
                     f'cannot free another cell: {list(ignored)}')
    if same_result is False:
        notes.append('fewest masks and highest preserved release value are different plans: '
                     f'fewest masks {minimum["extra_masked"]} '
                     f'(value {minimum["preserved_value"]}), value plan '
                     f'{best["extra_masked"]} (value {best["preserved_value"]})')
    if status == 'partial':
        notes.append('search stopped before every combination was decided; the recommended plan '
                     'is verified by review but optimality is not certified')
    if status == 'incomplete':
        notes.append('search did not finish and no verified plan was found; no plan is offered')
    if status == 'unsatisfiable' and reason == 'release_value_target_unreachable':
        notes.append('lower min_release_value or allow more cells to be masked; no plan is offered')
    if status == 'unsatisfiable' and reason == 'no_combination_passes_review':
        notes.append('relax one of required_public or widen maskable; no plan is offered')

    plans = feasible[:_MAX_PLANS]
    if recommended is not None and recommended not in plans:
        plans = [recommended] + plans
    if best is not None and best not in plans:
        plans = plans + [best]
    if minimum is not None and minimum not in plans:
        plans = [minimum] + plans
    shown = {tuple(plan['extra_masked']) for plan in plans}
    truncated = any(tuple(plan['extra_masked']) not in shown for plan in feasible)

    return {
        'table': table,
        'status': status,
        'reason': reason,
        'constraints': {
            'required_public': list(spec['required_public']),
            'maskable': list(spec['maskable']),
            'release_values': dict(sorted(values.items())),
            'min_release_value': target,
            'node_budget': spec['node_budget'],
            'search_budget': spec['search_budget'],
        },
        'protected_original_masked': list(originals),
        'ignored_maskable': list(ignored),
        'search': {
            'candidate_cells': list(candidates),
            'subsets_evaluated': search['evaluated'],
            'dominated_subsets_skipped': search['pruned'],
            'inconclusive_views': search['inconclusive'],
            'exhaustive': search['complete'],
            'nodes_used': search['nodes'],
        },
        'plans': plans,
        'plans_truncated': truncated,
        'minimum_mask': minimum,
        'minimum_mask_certified': minimum_certified,
        'best_value': best,
        'best_value_certified': best_certified,
        'recommended': recommended,
        'recommended_certified': recommended_certified,
        'same_result': same_result,
        'unsatisfiable': detail,
        'notes': notes,
    }
