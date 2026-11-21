from .constraints import compile_view
from .model import MAX_CANDIDATE_MINIMUM
from .search import Exhausted, Solver

LEGACY_MINIMUM = 2


def review(limit, cells, equations, budget, policy=None):
    """Audit a single table.

    ``policy`` maps masked cell IDs to the minimum number of mutually distinct
    feasible integer candidates that cell must have, the observed value
    included.  A masked cell absent from ``policy`` keeps the legacy
    requirement: at least one feasible value other than the observed one.
    ``policy`` must be empty for callers that do not opt into the stricter
    protection, so the legacy response shape is preserved exactly.
    """
    if type(budget) is not int or not 1 <= budget <= 5000:
        raise ValueError('node budget must be between 1 and 5000')
    policy = dict(policy or {})
    for key, minimum in policy.items():
        if key not in cells or cells[key].mode != 'masked':
            raise ValueError('candidate policy is only valid for masked cells')
        if type(minimum) is not int or not 1 <= minimum <= MAX_CANDIDATE_MINIMUM:
            raise ValueError('minimum candidates must be an integer between 1 and 257')
    observed, linear = compile_view(cells, equations)
    domains = {key: observed.get(key, (0, limit)) for key in sorted(cells)}
    solver = Solver(linear, budget)
    results, details = {}, {}
    for key, cell in sorted(cells.items()):
        if cell.mode != 'masked':
            continue
        if key not in policy:
            try:
                witnessed = solver.has_alternative(domains, key, cell.count)
            except Exhausted:
                results[key] = 'indeterminate'
            else:
                results[key] = 'alternative_exists' if witnessed else 'uniquely_determined'
            continue
        required = policy[key]
        try:
            found, exact = solver.count_distinct(domains, key, cell.count, required)
        except Exhausted:
            results[key] = 'indeterminate'
            details[key] = {'minimum': required, 'found': None, 'exact': False, 'satisfied': False}
            continue
        satisfied = found >= required
        results[key] = 'candidates_sufficient' if satisfied else 'insufficient_candidates'
        details[key] = {'minimum': required, 'found': found, 'exact': exact, 'satisfied': satisfied}
    allowed = {'alternative_exists', 'candidates_sufficient'}
    result = {'decision': 'allow' if all(value in allowed for value in results.values()) else 'hold',
              'cells': results, 'nodes_used': budget - solver.remaining}
    if policy:
        result['candidates'] = details
    return result
