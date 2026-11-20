import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator

from release.app import application


def run(probe):
    with TemporaryDirectory() as directory:
        db_path = Path(directory) / 'demo.sqlite3'
        app = validator(application(db_path))

        def request(method, path, data=None, expected=200, reopen=False):
            env = {}
            setup_testing_defaults(env)
            body = json.dumps(data).encode() if data is not None else b''
            env.update({'REQUEST_METHOD': method, 'PATH_INFO': path, 'CONTENT_LENGTH': str(len(body)),
                        'CONTENT_TYPE': 'application/json', 'wsgi.input': io.BytesIO(body), 'QUERY_STRING': ''})
            statuses = []

            def begin(status, headers, exc_info=None):
                statuses.append(int(status.split()[0]))

            handler = validator(application(db_path)) if reopen else app
            response = handler(env, begin)
            try:
                content = json.loads(b''.join(response))
            finally:
                response.close()
            if statuses != [expected]:
                raise AssertionError(f'{method} {path}: expected {expected}, got {statuses}: {content}')
            return content

        print(json.dumps(probe(request), ensure_ascii=False, sort_keys=True))
