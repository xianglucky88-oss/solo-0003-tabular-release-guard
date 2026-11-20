import argparse
import json
from wsgiref.simple_server import make_server

from .service import dispatch
from .store import NotFound, Store


def application(path):
    store = Store(path)

    def handle(environ, start_response):
        method, route = environ['REQUEST_METHOD'], environ['PATH_INFO']
        status = '200 OK'
        try:
            data = {}
            if method == 'POST':
                length = int(environ.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= 1_000_000:
                    raise ValueError('body must be 1 to 1000000 bytes')
                data = json.loads(environ['wsgi.input'].read(length))
                if not isinstance(data, dict):
                    raise ValueError('expected a JSON object')
            if route == '/health' and method == 'GET':
                result = {'service': 'release', 'status': 'ok'}
            else:
                result = dispatch(method, route, data, store)
        except NotFound as exc:
            result, status = {'error': str(exc)}, '404 Not Found'
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            result, status = {'error': f'invalid request: {exc}'}, '400 Bad Request'
        encoded = json.dumps(result, sort_keys=True, allow_nan=False).encode()
        start_response(status, [('Content-Type', 'application/json'), ('Content-Length', str(len(encoded)))])
        return [encoded]

    return handle


def main():
    parser = argparse.ArgumentParser(description='Start the local data service')
    parser.add_argument('--port', type=int, default=8763)
    parser.add_argument('--db', default='release-artifacts.sqlite3')
    args = parser.parse_args()
    with make_server('127.0.0.1', args.port, application(args.db)) as server:
        print(f'Listening at http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
