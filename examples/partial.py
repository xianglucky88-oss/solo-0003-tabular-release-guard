from copy import deepcopy
import json
from pathlib import Path

from release.model import parse
from release.review import review


def load():
    return json.loads(Path(__file__).with_name('mixed.json').read_text())


def renamed(payload, prefix):
    """Give every cell a fresh identifier, keeping structure and counts."""
    mapped = {cell['id']: f'{prefix}{index:02d}'
              for index, cell in enumerate(sorted(payload['cells'], key=lambda c: c['id']))}
    renamed = deepcopy(payload)
    for cell in renamed['cells']:
        cell['id'] = mapped[cell['id']]
    for relation in renamed['relations']:
        relation['total'] = mapped[relation['total']]
        relation['terms'] = [mapped[term] for term in relation['terms']]
    return renamed, mapped


def verify():
    payload = load()
    table, limit, cells, equations = parse(payload)

    # Low budget: the independent simple region must answer before the hard
    # region has had a chance to drain the budget.
    low = review(limit, cells, equations, 4)
    assert low['decision'] == 'hold'
    assert low['nodes_used'] <= 4
    assert low['cells']['meadow-a'] == 'uniquely_determined'
    assert low['cells']['homes-north'] == 'alternative_exists'
    assert low['cells']['homes-south'] == 'alternative_exists'
    assert {key for key, value in low['cells'].items() if value == 'indeterminate'} >= {
        'g00', 'g11', 'g22'}

    # The table is mixed: one hard, tightly coupled region (g*) and independent
    # simple regions (homes, meadow).  Even the smallest budgets answer the
    # simple questions and never let the hard region starve them.
    for budget in range(1, 200):
        result = review(limit, cells, equations, budget)
        assert 0 <= result['nodes_used'] <= budget
    # Progress only grows with the budget: a verdict once reached is never
    # withdrawn, so a larger budget can only confirm more.
    for budget in range(2, 200):
        before = review(limit, cells, equations, budget - 1)
        after = review(limit, cells, equations, budget)
        for key, value in before['cells'].items():
            assert value == 'indeterminate' or after['cells'][key] == value, (budget, key)

    # Ample budget: the hard region is settled too, and the simple cells keep
    # their earlier verdicts.
    ample = review(limit, cells, equations, 300)
    assert ample['decision'] == 'hold'
    assert ample['nodes_used'] <= 300
    assert all(ample['cells'][key] == low['cells'][key]
               for key in ('meadow-a', 'homes-north', 'homes-south'))
    assert all(value != 'indeterminate' for value in ample['cells'].values())
    assert ample['cells']['g00'] == 'alternative_exists'

    # Renaming and reordering must not change which independent simple
    # questions are confirmed first at the tight budget.
    for prefix in ('q', 'zz', 'cell_'):
        alias, mapping = renamed(payload, prefix)
        shuffled = deepcopy(alias)
        shuffled['cells'].reverse()
        shuffled['relations'].reverse()
        for relation in shuffled['relations']:
            relation['terms'].reverse()
        _, alias_limit, alias_cells, alias_equations = parse(shuffled)
        alias_low = review(alias_limit, alias_cells, alias_equations, 4)
        expected = {mapping[key]: value for key, value in low['cells'].items()}
        assert alias_low['cells'] == expected, (prefix, alias_low['cells'], expected)
        assert alias_low['nodes_used'] == low['nodes_used']

    # Node accounting is exact: a run that ends early reports what it spent,
    # and every budget is respected.
    for budget in (1, 2, 3, 5, 8, 16, 32, 64, 300):
        result = review(limit, cells, equations, budget)
        assert 0 <= result['nodes_used'] <= budget
        assert result['nodes_used'] == review(limit, cells, equations, budget)['nodes_used']

    return {
        'low_budget': {'budget': 4, 'nodes_used': low['nodes_used'], 'cells': low['cells']},
        'ample_budget': {'budget': 300, 'nodes_used': ample['nodes_used'], 'cells': ample['cells']},
        'rename_stable': True,
    }


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, sort_keys=True))
