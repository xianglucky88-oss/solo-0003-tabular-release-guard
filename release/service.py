from .store import NotFound
from .model import parse
from .publication import manifest
from .review import review


def dispatch(method, path, data, store):
    if method == 'POST' and path in ('/release/reviews', '/release/publications'):
        table, limit, cells, equations = parse(data)
        decision = review(limit, cells, equations, data.get('node_budget', 300))
        if path == '/release/reviews':
            return {'table': table, **decision}
        if decision['decision'] != 'allow':
            raise ValueError('publication held: review did not establish alternatives for every masked cell')
        result = manifest(table, limit, cells, equations)
        return {'id': store.put('publication', result), **result}
    if method == 'GET' and path.startswith('/release/publications/'):
        key = path.removeprefix('/release/publications/')
        return {'id': key, **store.get('publication', key)}
    raise NotFound('unknown release endpoint')
