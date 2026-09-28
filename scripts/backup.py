"""Create a consistent SQLite backup; send the result off-host with restic."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

source = Path(os.environ.get("DATABASE_PATH", "data/growth.db"))
target_dir = Path(os.environ.get("BACKUP_DIR", "backups"))
if not source.is_file():
    raise SystemExit(f"Database does not exist: {source}")
target_dir.mkdir(parents=True, exist_ok=True)
target = target_dir / f"growth-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.db"
with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
    src.backup(dst)
    healthy = dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
if not healthy:
    target.unlink(missing_ok=True)
    raise SystemExit("Backup integrity check failed")
print(target)
