"""SQLite adapter. Scoped records and optimistic concurrency for every mutation."""
import json
from contextlib import contextmanager
from typing import Protocol
from ..db import transaction
from ..common import uid
from ..security import iso
from .domain import Conflict


class RecordStore(Protocol):
    def list(self, kind: str) -> list[dict]: ...
    def get(self, kind: str, key: str) -> dict: ...
    def save(self, kind: str, data: dict, key: str | None = None, version: int | None = None) -> dict: ...
    def delete(self, kind: str, key: str, version: int) -> None: ...
    def event(self, kind: str, detail: dict, day: str | None = None) -> None: ...


class SQLiteRecords:
    def __init__(self, db, user_id):
        self.db, self.user_id = db, user_id

    @staticmethod
    def decode(row):
        return {**json.loads(row['payload']), 'id': row['id'], 'version': row['version'], 'created_at': row['created_at'], 'updated_at': row['updated_at']}

    def list(self, kind):
        return [self.decode(r) for r in self.db.execute('SELECT * FROM planner_records WHERE user_id=? AND kind=? ORDER BY created_at DESC', (self.user_id, kind))]

    def get(self, kind, key):
        row = self.db.execute('SELECT * FROM planner_records WHERE user_id=? AND kind=? AND id=?', (self.user_id, kind, key)).fetchone()
        if not row:
            raise KeyError('记录不存在')
        return self.decode(row)

    def save(self, kind, data, key=None, version=None):
        payload = {k: v for k, v in data.items() if k not in ('id', 'version', 'created_at', 'updated_at')}
        stamp = iso()
        if key:
            before = self.get(kind, key)
            if version is None or before['version'] != version:
                raise Conflict('内容已更新，请刷新后重试')
            self.db.execute('UPDATE planner_records SET payload=?,version=version+1,updated_at=? WHERE user_id=? AND id=?', (json.dumps(payload, ensure_ascii=False), stamp, self.user_id, key))
        else:
            key = uid()
            self.db.execute('INSERT INTO planner_records VALUES(?,?,?,?,1,?,?)', (key, self.user_id, kind, json.dumps(payload, ensure_ascii=False), stamp, stamp))
        return self.get(kind, key)

    def delete(self, kind, key, version):
        if self.get(kind, key)['version'] != version:
            raise Conflict('内容已更新，请刷新后重试')
        self.db.execute('DELETE FROM planner_records WHERE user_id=? AND kind=? AND id=?', (self.user_id, kind, key))

    def event(self, kind, detail, day=None):
        from .domain import today
        self.save('journal_event', {'kind': kind, 'date': day or today(), 'detail': detail})


@contextmanager
def records(user_id):
    with transaction() as db:
        yield SQLiteRecords(db, user_id)
