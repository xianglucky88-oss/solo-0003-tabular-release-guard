import hashlib
import json
import sqlite3
from contextlib import closing


class NotFound(LookupError):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS artifacts ("
                       "kind TEXT, digest TEXT, payload BLOB NOT NULL, PRIMARY KEY (kind, digest))")

    def put(self, kind, value):
        payload = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        key = hashlib.sha256(kind.encode() + b'\0' + payload).hexdigest()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('INSERT OR IGNORE INTO artifacts VALUES (?, ?, ?)', (kind, key, payload))
        return key

    def get(self, kind, key):
        if not isinstance(key, str):
            raise ValueError('expected an artifact ID')
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT payload FROM artifacts WHERE kind=? AND digest=?', (kind, key)).fetchone()
        if row is None:
            raise NotFound('artifact not found')
        return json.loads(row[0])
