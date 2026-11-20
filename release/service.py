from .store import NotFound
from .model import parse, parse_manifest
from .publication import manifest
from .review import review
from .crossreview import UnsupportedMapping, cross_review


def _load_reference(store, reference_id):
    if not isinstance(reference_id, str):
        raise UnsupportedMapping('reference must be a stored publication id')
    return parse_manifest(store.get('publication', reference_id))


def dispatch(method, path, data, store):
    if method == 'POST' and path in ('/release/reviews', '/release/publications'):
        table, limit, cells, equations = parse(data)
        decision = review(limit, cells, equations, data.get('node_budget', 300))
        if path == '/release/reviews':
            return {'table': table, **decision}
        if decision['decision'] != 'allow':
            raise ValueError('publication held: review did not establish alternatives for every masked cell')
        if 'reference' in data:
            mapping = data.get('mapping')
            if not isinstance(mapping, dict):
                raise UnsupportedMapping('publication against a reference requires a verifiable mapping')
            reference = _load_reference(store, data['reference'])
            cross = cross_review(reference, (table, limit, cells, equations),
                                 mapping, data.get('node_budget', 300))
            if cross['decision'] != 'allow':
                raise ValueError('publication held: cross-release review did not pass')
        result = manifest(table, limit, cells, equations)
        return {'id': store.put('publication', result), **result}
    if method == 'POST' and path == '/release/cross-reviews':
        table, limit, cells, equations = parse(data['candidate'])
        reference = _load_reference(store, data['reference'])
        mapping = data.get('mapping')
        if not isinstance(mapping, dict):
            raise UnsupportedMapping('cross-release review requires a verifiable mapping')
        decision = cross_review(reference, (table, limit, cells, equations),
                                mapping, data.get('node_budget', 300))
        return decision
    if method == 'GET' and path.startswith('/release/publications/'):
        key = path.removeprefix('/release/publications/')
        return {'id': key, **store.get('publication', key)}
    raise NotFound('unknown release endpoint')
