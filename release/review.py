from .constraints import compile_view
from .search import Exhausted, Solver


def review(limit, cells, equations, budget):
    if type(budget) is not int or not 1 <= budget <= 5000:
        raise ValueError('node budget must be between 1 and 5000')
    observed, linear = compile_view(cells, equations)
    domains = {key: observed.get(key, (0, limit)) for key in sorted(cells)}
    solver = Solver(linear, budget)
    results = {}
    for key, cell in sorted(cells.items()):
        if cell.mode != 'masked':
            continue
        try:
            ranges = [(0, cell.count - 1), (cell.count + 1, limit)]
            witnessed = any(solver.feasible({**domains, key: bounds}) for bounds in ranges if bounds[0] <= bounds[1])
            results[key] = 'alternative_exists' if witnessed else 'uniquely_determined'
        except Exhausted:
            results[key] = 'indeterminate'
    return {'decision': 'allow' if all(v == 'alternative_exists' for v in results.values()) else 'hold',
            'cells': results, 'nodes_used': budget - solver.remaining}
