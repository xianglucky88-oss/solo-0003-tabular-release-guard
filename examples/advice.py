"""Editor-facing masking advice demo on synthetic cross-margin data.

The advice endpoint only proposes.  This demo takes the proposal an editor
would accept, turns it into an ordinary table submission, and shows that the
existing review/publication workflow accepts it unchanged.
"""

from copy import deepcopy
import json
from pathlib import Path

from .client import run


BASE = Path(__file__).with_name('cross-margins.json')


def load():
    return json.loads(BASE.read_text())


def apply_plan(table, plan):
    """Editor action: mark the advised cells masked; counts are not altered."""
    updated = deepcopy(table)
    chosen = set(plan['extra_masked'])
    for cell in updated['cells']:
        if cell['id'] in chosen:
            cell['mode'] = 'masked'
    return updated


def probe(request):
    table = load()

    advice = request('POST', '/release/advice', {
        **table,
        'required_public': ['c1_total'],
        'maskable': ['r1c2', 'r1_total', 'r2_total', 'c2_total'],
        'release_values': {'r1c2': 100, 'c1_total': 1, 'r1_total': 1,
                           'r2_total': 1, 'c2_total': 1},
        'min_release_value': 102,
        'node_budget': 300,
    })
    assert advice['status'] == 'ok' and advice['recommended'] is not None
    assert advice['recommended_certified'] is True
    assert advice['same_result'] is False, 'demo expects the two objectives to diverge'
    assert advice['minimum_mask']['mask_count'] == 1
    assert advice['recommended']['mask_count'] == 2

    # The advised view must pass the ordinary review before anything is stored.
    advised_table = apply_plan(table, advice['recommended'])
    reviewed = request('POST', '/release/reviews', advised_table)
    assert reviewed['decision'] == 'allow'
    # A newly masked cell that the remaining relations still pin down would
    # appear as 'uniquely_determined' here; every masked cell must have an
    # alternative instead.
    assert set(reviewed['cells'].values()) == {'alternative_exists'}

    # The proposal also has to be publishable through the existing endpoint,
    # and the artifact must not leak masked counts.
    published = request('POST', '/release/publications', advised_table)
    assert all('count' not in cell for cell in published['cells']
               if cell['mode'] == 'masked')
    assert request('GET', '/release/publications/' + published['id'], reopen=True) == published

    # Unsatisfiable request: nothing is offered, and the cause names the
    # requirement that blocks every candidate view.
    stuck = request('POST', '/release/advice', {
        **table,
        'required_public': ['r1c2', 'r1_total'],
        'maskable': ['r2_total', 'c1_total', 'c2_total'],
        'release_values': {},
        'node_budget': 300,
    })
    assert stuck['status'] == 'unsatisfiable' and stuck['recommended'] is None
    assert stuck['unsatisfiable']['persistent_unique'] == ['r1c1']
    assert stuck['unsatisfiable']['relaxations']['complete'] is True

    # A review budget too small to finish must not be reported as usable.
    unfinished = request('POST', '/release/advice', {
        **table,
        'required_public': ['c1_total'],
        'maskable': ['r1c2', 'r1_total', 'r2_total', 'c2_total'],
        'release_values': {},
        'node_budget': 1,
        'search_budget': 8,
    })
    assert unfinished['status'] == 'incomplete' and unfinished['recommended'] is None

    # Requests that would step outside the editor's authority are rejected.
    request('POST', '/release/advice', {**table, 'required_public': ['void'],
                                        'maskable': []}, 400)
    request('POST', '/release/advice', {**table, 'required_public': [],
                                        'maskable': ['r2c2']}, 400)
    request('POST', '/release/advice', {**table, 'required_public': ['r1c2'],
                                        'maskable': ['r1c2']}, 400)

    return {
        'minimum_mask': advice['minimum_mask']['extra_masked'],
        'minimum_mask_value': advice['minimum_mask']['preserved_value'],
        'best_value_masks': advice['recommended']['extra_masked'],
        'best_value_preserved': advice['recommended']['preserved_value'],
        'same_result': advice['same_result'],
        'review': reviewed['decision'],
        'publication': 'stored',
        'unsatisfiable': stuck['status'],
        'incomplete_without_plan': unfinished['status'],
    }


if __name__ == '__main__':
    run(probe)
