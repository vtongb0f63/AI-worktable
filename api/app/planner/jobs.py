import json
from datetime import timedelta
from ..db import transaction, connect
from ..common import uid
from ..security import iso, now
from .domain import Conflict


def decode(row):
    data = dict(row)
    data['payload'] = json.loads(data['payload'])
    data['result'] = json.loads(data['result']) if data['result'] else None
    return data


def enqueue(user_id, kind, payload, dedup=None, priority=10):
    if len(json.dumps(payload)) > 100000:
        raise ValueError('请求内容过大')
    with transaction() as db:
        if dedup:
            existing = db.execute('SELECT * FROM planner_jobs WHERE dedup_key=?', (dedup,)).fetchone()
            if existing:
                return decode(existing)
        active = db.execute("SELECT count(*) FROM planner_jobs WHERE user_id=? AND status IN ('pending','running','blocked')", (user_id,)).fetchone()[0]
        if active >= 30:
            raise Conflict('待处理任务较多，请等待或取消旧任务')
        key, stamp = uid(), iso()
        db.execute('INSERT INTO planner_jobs(id,user_id,kind,payload,dedup_key,priority,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)', (key, user_id, kind, json.dumps(payload, ensure_ascii=False), dedup, priority, stamp, stamp))
        return decode(db.execute('SELECT * FROM planner_jobs WHERE id=?', (key,)).fetchone())


def list_jobs(user_id):
    with connect() as db:
        return [decode(r) for r in db.execute('SELECT * FROM planner_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 30', (user_id,))]


def change_job(user_id, key, action):
    with transaction() as db:
        row = db.execute('SELECT * FROM planner_jobs WHERE id=? AND user_id=?', (key, user_id)).fetchone()
        if not row:
            raise KeyError('任务不存在')
        if action == 'retry':
            if row['status'] not in ('blocked', 'failed'):
                raise Conflict('只能重试失败或等待中的任务')
            db.execute("UPDATE planner_jobs SET status='pending',error=NULL,retry_at=NULL,attempts=0,updated_at=? WHERE id=?", (iso(), key))
        elif action == 'cancel':
            if row['status'] == 'done':
                raise Conflict('任务已经完成')
            db.execute("UPDATE planner_jobs SET status='cancelled',updated_at=? WHERE id=?", (iso(), key))
        else:
            raise ValueError('无效操作')
        return decode(db.execute('SELECT * FROM planner_jobs WHERE id=?', (key,)).fetchone())


def claim():
    with transaction() as db:
        # A crashed worker's lease is recoverable; there is only one deployed worker.
        db.execute("UPDATE planner_jobs SET status='pending' WHERE status='running' AND updated_at<?", (iso(now() - timedelta(minutes=15)),))
        row = db.execute("SELECT * FROM planner_jobs WHERE status='pending' OR (status='blocked' AND retry_at IS NOT NULL AND retry_at<=?) ORDER BY priority,created_at LIMIT 1", (iso(),)).fetchone()
        if not row:
            return None
        db.execute("UPDATE planner_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=?", (iso(), row['id']))
        return decode(db.execute('SELECT * FROM planner_jobs WHERE id=?', (row['id'],)).fetchone())
