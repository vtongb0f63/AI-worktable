import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DATABASE_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, username TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, verified_at TEXT, is_admin INTEGER NOT NULL DEFAULT 0,
 start_date TEXT, timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
 created_at TEXT NOT NULL, deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS invites (
 code_hash TEXT PRIMARY KEY, created_by TEXT, uses_left INTEGER NOT NULL,
 expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verification_tokens (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 parent_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('vision','year','semester','month','week','task')),
 title TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
 starts_on TEXT, ends_on TEXT, due_on TEXT,
 weight REAL NOT NULL DEFAULT 1 CHECK(weight > 0),
 is_public INTEGER NOT NULL DEFAULT 0, is_done INTEGER NOT NULL DEFAULT 0,
 is_main INTEGER NOT NULL DEFAULT 0, is_week_focus INTEGER NOT NULL DEFAULT 0,
 position INTEGER NOT NULL DEFAULT 0, hidden_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_nodes_user_parent ON nodes(user_id,parent_id);
CREATE INDEX IF NOT EXISTS ix_nodes_user_due ON nodes(user_id,due_on);
CREATE TABLE IF NOT EXISTS node_versions (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 node_id TEXT NOT NULL, version INTEGER NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(node_id,version)
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 node_id TEXT, kind TEXT NOT NULL, detail TEXT NOT NULL, occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_events_user_time ON events(user_id,occurred_at);
CREATE TABLE IF NOT EXISTS ai_keys (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 ciphertext TEXT NOT NULL, suffix TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_usage (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 day TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, busy INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(user_id,day)
);
CREATE TABLE IF NOT EXISTS reports (
 id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 node_id TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
 reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 key TEXT PRIMARY KEY, count INTEGER NOT NULL, window_start TEXT NOT NULL
);
"""


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db


MIGRATIONS = {1: SCHEMA}


def init_db():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        for next_version in sorted(MIGRATIONS):
            if next_version > version:
                db.executescript(MIGRATIONS[next_version])
                db.execute(f"PRAGMA user_version={next_version}")
        db.execute("UPDATE ai_usage SET busy=0")
        cutoff = datetime.now(timezone.utc).isoformat()
        db.execute("DELETE FROM sessions WHERE expires_at<?", (cutoff,))
        db.execute("DELETE FROM verification_tokens WHERE expires_at<?", (cutoff,))


@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
