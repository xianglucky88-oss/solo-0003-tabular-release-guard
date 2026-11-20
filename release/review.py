from .constraints import compile_view
from .search import Solver

# Per-cell outcomes.  Only ``alternative_exists`` clears a cell for
# publication; ``uniquely_determined`` and ``indeterminate`` both hold the
# table, because the masked count could not be shown to admit several values.
ALTERNATIVE = 'alternative_exists'
UNIQUE = 'uniquely_determined'
PENDING = 'indeterminate'


def _components(cells, equations):
    """Split the table into independent regions.

    Cells belong to the same region when one relation mentions both, so a
    region can be searched on its own: no relation ties it to another region.
    """
    parent = {key: key for key in cells}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def join(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for equation in equations:
        keys = [equation.total, *equation.terms]
        for member in keys[1:]:
            join(keys[0], member)
    groups = {}
    for key in cells:
        groups.setdefault(find(key), []).append(key)
    return groups


def _refine(group, cells, equations):
    """Canonical per-cell labels from disclosure mode, count and structure.

    Labels start from each cell's mode and count and are refined by folding in,
    for every relation touching the cell, whether the cell is the total or a
    term and the labels of the relation's other cells.  Distinct signatures are
    replaced by small integers in sorted order, so the labels stay compact and
    canonical.  No identifier is ever read, so the labels -- and any order
    derived from them -- stay the same when masked cells are renamed or the
    request is reordered.  Cells left with the same label are structurally
    interchangeable: any permutation of them that also permutes the relations
    is a symmetry of the model.
    """
    members = set(group)
    touching = {key: [] for key in group}
    for equation in equations:
        keys = [equation.total, *equation.terms]
        if not members.intersection(keys):
            continue
        for key in keys:
            if key in members:
                touching[key].append(equation)

    labels = {key: (cells[key].mode, cells[key].count) for key in group}
    for _ in range(len(group) + 1):
        signatures = {}
        for key in group:
            around = []
            for equation in touching[key]:
                role = 'total' if equation.total == key else 'term'
                peers = tuple(sorted(labels[other] for other in equation.terms if other != key))
                if equation.total != key:
                    peers += (('total', labels[equation.total]),)
                around.append((role, len(equation.terms), peers))
            signatures[key] = (cells[key].mode, cells[key].count, tuple(sorted(around, key=repr)))
        distinct = {signature: index for index, signature in
                    enumerate(sorted(set(signatures.values()), key=repr))}
        refined = {key: distinct[signatures[key]] for key in group}
        if refined == labels:
            break
        labels = refined
    return labels


def _region_key(group, cells, equations, labels):
    """Identifier-free signature of a whole region, used to rank regions.

    Regions are ordered by how many masked cells they ask about -- the fewer,
    the likelier propagation alone settles them -- then by size and by the
    canonical labels.  Two regions with the same key are isomorphic as
    constraint systems with the same disclosure modes and counts.
    """
    members = set(group)
    relations = tuple(sorted(
        (labels[equation.total], tuple(sorted(labels[term] for term in equation.terms)))
        for equation in equations if members.intersection((equation.total, *equation.terms))
    ))
    masked = sum(1 for key in group if cells[key].mode == 'masked')
    return (masked, len(group), tuple(sorted(labels[key] for key in group)), relations)


def review(limit, cells, equations, budget):
    if type(budget) is not int or not 1 <= budget <= 5000:
        raise ValueError('node budget must be between 1 and 5000')
    observed, linear = compile_view(cells, equations)
    solver = Solver(budget)

    # Two questions per masked cell: may it fall below its observed count, and
    # may it rise above?  One feasible side proves an alternative allocation;
    # two infeasible sides prove the count uniquely determined.
    questions = {}
    for key, cell in cells.items():
        if cell.mode != 'masked':
            continue
        sides = []
        for bounds in ((0, cell.count - 1), (cell.count + 1, limit)):
            if bounds[0] <= bounds[1]:
                sides.append({'bounds': bounds, 'state': None})
        questions[key] = sides

    def settled(key):
        sides = questions[key]
        return any(side['state'] is True for side in sides) or all(side['state'] is False for side in sides)

    def active_sides(order):
        """The one side of each unsettled cell to work on next.

        Sides are tried in a fixed order (below the count first, then above
        it).  As soon as one side is confirmed -- a witness or a contradiction
        -- the cell is settled, so the other side is never searched.  A cell
        with both sides contradicted is uniquely determined.
        """
        active = []
        for key in order:
            if settled(key):
                continue
            for side in questions[key]:
                if side['state'] is None:
                    active.append((key, side))
                    break
        return active

    def ask(key, side, allowance):
        """Continue one question against that cell's own region, spending at
        most ``allowance`` nodes.  Returns True/False, or None if
        inconclusive; an inconclusive search keeps its stack for next time, so
        no node is ever spent twice on the same question.
        """
        local, relations = regions[key]
        low, high = side['bounds']
        base_low, base_high = local[key]
        low, high = max(low, base_low), min(high, base_high)
        if low > high:
            return False
        if side.get('stack') is None:
            side['stack'] = [{**local, key: (low, high)}]
        return solver.step(side['stack'], relations, allowance, ranks)

    # Each region is searched over its own cells and relations only, so free
    # cells elsewhere cannot stop propagation from settling it.
    components = list(_components(cells, equations).values())
    labels = {}
    regions = {}
    ranks = {}
    for group in components:
        group_labels = _refine(group, cells, equations)
        labels.update(group_labels)
        members = set(group)
        local = {key: observed.get(key, (0, limit)) for key in sorted(group)}
        relations = [dict(equation) for equation in linear
                     if members.intersection(equation)]
        for key in group:
            regions[key] = (local, relations)
            ranks[key] = (group_labels[key],)

    classes = {}
    for group in components:
        classes.setdefault(_region_key(group, cells, equations, labels), []).append(group)
    ranked = [classes[signature] for signature in sorted(classes, key=repr)]

    # Work list: independent regions cheapest-shaped first, then cells by
    # canonical label.  Regions in one class are isomorphic and cells sharing a
    # label inside the class are structurally interchangeable, so they are
    # bucketed together -- across sibling regions too -- and advance together
    # regardless of the order the request happens to list them in.
    buckets = []
    for groups in ranked:
        ties = {}
        for group in groups:
            for key in group:
                if key in questions:
                    ties.setdefault(labels[key], []).append(key)
        for label in sorted(ties):
            buckets.append(ties[label])

    # The work list is fixed above: independent regions cheapest-shaped first,
    # then cells by canonical label, with interchangeable cells kept in one
    # bucket so they always advance together.  Pass k gives each cell a quota of
    # 2**k nodes and, within that quota, serves its open sides one node at a
    # time.  A cheap cell needs exactly one node per side to prove both sides
    # contradictory, so it is settled in the first pass -- before a difficult
    # region is ever served.  Because the quota depends only on the pass
    # number, the node sequence is the same whatever the budget: a smaller
    # budget stops earlier in it, so more budget only ever confirms more and
    # never retracts a confirmation.  Each search resumes its own stack, so no
    # node is spent twice.
    quota = 2
    while solver.remaining > 0:
        for bucket in buckets:
            for key in bucket:
                spent = 0
                while spent < quota and solver.remaining > 0:
                    pending = active_sides([key])
                    if not pending:
                        break
                    item_key, side = pending[0]
                    before = solver.remaining
                    verdict = ask(item_key, side, 1)
                    spent += before - solver.remaining
                    if verdict is not None:
                        side['state'] = verdict
            if solver.remaining <= 0:
                break
        if quota >= budget:
            break
        quota *= 2

    results = {}
    for key, sides in questions.items():
        if any(side['state'] is True for side in sides):
            results[key] = ALTERNATIVE
        elif sides and all(side['state'] is False for side in sides):
            results[key] = UNIQUE
        else:
            results[key] = PENDING
    # Structurally interchangeable cells have identical true verdicts.  If the
    # budget ran out before all of them were settled, one member may look
    # confirmed while a twin is still pending; demote the whole group so a
    # rename or reorder cannot change which identical cell appears confirmed.
    for bucket in buckets:
        if any(results[key] == PENDING for key in bucket):
            for key in bucket:
                results[key] = PENDING
    return {'decision': 'allow' if all(v == ALTERNATIVE for v in results.values()) else 'hold',
            'cells': results, 'nodes_used': budget - solver.remaining}
