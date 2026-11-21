from copy import deepcopy
import json
from pathlib import Path
from .client import run


def load(name):
    return json.loads(Path(__file__).with_name(name).read_text())


def probe(request):
    data = load('region.json')
    allowed = request('POST', '/release/reviews', data)
    assert allowed['decision'] == 'allow' and set(allowed['cells'].values()) == {'alternative_exists'}
    single = deepcopy(data)
    single['cells'][2]['mode'] = 'public'
    held = request('POST', '/release/reviews', single)
    assert held['decision'] == 'hold' and held['cells'] == {'ridge': 'uniquely_determined'}
    budget = request('POST', '/release/reviews', {**data, 'node_budget': 1})
    assert budget['decision'] == 'hold' and 'indeterminate' in budget['cells'].values()
    request('POST', '/release/publications', single, 400)
    request('POST', '/release/reviews', {**data, 'relations': [{**data['relations'][0], 'terms': ['ridge']}]}, 400)
    publication = request('POST', '/release/publications', data)
    assert 'nodes_used' not in publication and all('count' not in c for c in publication['cells'] if c['mode'] == 'masked')
    reissue = deepcopy(data)
    reissue['cells'][1]['count'], reissue['cells'][2]['count'] = 4, 5
    assert request('POST', '/release/publications', reissue) == publication
    assert request('GET', '/release/publications/' + publication['id'], reopen=True) == publication
    request('GET', '/release/publications/absent', expected=404)

    # Same per-cell public range (0..4), different number of feasible integers.
    contiguous, sparse = load('candidates_contiguous.json'), load('candidates_sparse.json')
    for table in (contiguous, sparse):
        legacy = request('POST', '/release/reviews', table)
        assert legacy['decision'] == 'allow' and 'candidates' not in legacy
        assert set(legacy['cells'].values()) == {'alternative_exists'}

    policy = {'c1': 4}
    dense = request('POST', '/release/reviews', {**contiguous, 'min_candidates': policy})
    narrow = request('POST', '/release/reviews', {**sparse, 'min_candidates': policy})
    assert dense['decision'] == 'allow'
    assert dense['candidates']['c1'] == {'minimum': 4, 'found': 4, 'exact': False, 'satisfied': True}
    assert narrow['decision'] == 'hold'
    assert narrow['candidates']['c1'] == {'minimum': 4, 'found': 3, 'exact': True, 'satisfied': False}
    # The spanning range is identical for both, so a max-minus-min count would
    # report five candidates for the sparse table and wrongly allow it.
    assert dense['candidates']['c1']['minimum'] == narrow['candidates']['c1']['minimum']

    starved = request('POST', '/release/reviews', {**sparse, 'min_candidates': policy, 'node_budget': 1})
    assert starved['decision'] == 'hold' and starved['candidates']['c1']['found'] is None
    assert 'indeterminate' in starved['cells'].values()

    request('POST', '/release/publications', {**sparse, 'min_candidates': policy}, 400)
    request('POST', '/release/reviews', {**sparse, 'min_candidates': {'c1': 0}}, 400)
    request('POST', '/release/reviews', {**sparse, 'min_candidates': {'c1': 258}}, 400)
    aliased = request('POST', '/release/reviews', {**sparse, 'minimum_candidates': policy})
    assert aliased['decision'] == 'hold'
    assert request('POST', '/release/reviews', {**sparse, 'required_candidates': policy})['decision'] == 'hold'
    request('POST', '/release/reviews',
            {**sparse, 'min_candidates': policy, 'minimum_candidates': {'c1': 3}}, 400)
    request('POST', '/release/reviews', {**sparse, 'min_candidates': {'c0': 3, 'total': 3}}, 400)
    request('POST', '/release/reviews', {**sparse, 'min_candidates': {'c1': True}}, 400)

    guarded = request('POST', '/release/publications', {**sparse, 'min_candidates': {'c0': 3, 'c1': 3, 'c2': 3, 'c3': 3}})
    assert guarded['protection']['standard'] == 'distinct_integer_candidates_per_masked_cell'
    assert guarded['protection']['candidate_minimums'] == {'c0': 3, 'c1': 3, 'c2': 3, 'c3': 3}
    assert all('count' not in c for c in guarded['cells'] if c['mode'] == 'masked')
    assert 'found' not in guarded and 'nodes_used' not in guarded
    reissued = deepcopy(sparse)
    for row in reissued['cells']:
        row['count'] = 0
    reissued['min_candidates'] = {'c0': 3, 'c1': 3, 'c2': 3, 'c3': 3}
    assert request('POST', '/release/publications', reissued) == guarded
    assert publication['protection']['candidate_minimums'] == {'ridge': 2, 'meadow': 2}

    return {'review': 'pass', 'publish': 'pass', 'retrieve': 'pass',
            'budget_holds': budget['decision'] == 'hold',
            'candidate_pair_distinguishes': dense['decision'] != narrow['decision']}


if __name__ == '__main__':
    run(probe)
