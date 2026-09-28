import json
import uuid
from fastapi import HTTPException

from .security import iso


def uid():
    return str(uuid.uuid4())


def owned_node(db, user_id, node_id):
    row = db.execute("SELECT * FROM nodes WHERE id=? AND user_id=?", (node_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "目标不存在")
    return dict(row)


def add_event(db, user_id, node_id, kind, detail):
    db.execute(
        "INSERT INTO events(id,user_id,node_id,kind,detail,occurred_at) VALUES(?,?,?,?,?,?)",
        (uid(), user_id, node_id, kind, json.dumps(detail, ensure_ascii=False), iso()),
    )


def save_version(db, node):
    version = db.execute(
        "SELECT COALESCE(MAX(version),0)+1 FROM node_versions WHERE node_id=?", (node["id"],)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO node_versions VALUES(?,?,?,?,?,?)",
        (uid(), node["user_id"], node["id"], version, json.dumps(node, ensure_ascii=False), iso()),
    )
