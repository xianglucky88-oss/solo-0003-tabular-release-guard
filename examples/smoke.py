from copy import deepcopy
import json
from pathlib import Path
from .client import run


def probe(request):
    data = json.loads(Path(__file__).with_name('region.json').read_text())
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
    return {'review': 'pass', 'publish': 'pass', 'retrieve': 'pass', 'budget_holds': budget['decision'] == 'hold'}


if __name__ == '__main__':
    run(probe)
