import json
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .common import add_event, owned_node, save_version, uid
from .db import connect, transaction
from .security import iso, require_admin, require_user

router = APIRouter(prefix="/api")
PARENTS = {"vision": None, "year": "vision", "semester": "year", "month": "semester", "week": "month", "task": "week"}


class NodeInput(BaseModel):
    parent_id: str | None = None
    kind: str
    title: str = Field(min_length=1, max_length=160)
    note: str = Field(default="", max_length=5000)
    starts_on: str | None = None
    ends_on: str | None = None
    due_on: str | None = None
    weight: float = Field(default=1, gt=0, le=1000)
    is_public: bool = False
    position: int = 0


class NodeUpdate(BaseModel):
    kind: str | None = None
    parent_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    note: str | None = Field(default=None, max_length=5000)
    starts_on: str | None = None
    ends_on: str | None = None
    due_on: str | None = None
    weight: float | None = Field(default=None, gt=0, le=1000)
    is_public: bool | None = None
    position: int | None = None
    is_main: bool | None = None
    is_week_focus: bool | None = None
    is_done: bool | None = None


def check_dates(values):
    for field in ("starts_on", "ends_on", "due_on"):
        if values.get(field):
            try:
                date.fromisoformat(values[field])
            except ValueError:
                raise HTTPException(422, f"{field} 日期无效")
    if values.get("starts_on") and values.get("ends_on") and values["starts_on"] > values["ends_on"]:
        raise HTTPException(422, "结束日期早于开始日期")


def compute_progress(rows, public=False):
    items = {row["id"]: dict(row) for row in rows if not public or row["is_public"] and not row["hidden_at"]}
    children = {}
    for row in items.values():
        children.setdefault(row["parent_id"], []).append(row)
    memo = {}

    def progress(node_id):
        if node_id in memo:
            return memo[node_id]
        node = items[node_id]
        descendants = children.get(node_id, [])
        if descendants:
            total = sum(child["weight"] for child in descendants)
            result = sum(progress(child["id"]) * child["weight"] for child in descendants) / total
        else:
            result = 100.0 if node["is_done"] else 0.0
        memo[node_id] = round(result, 1)
        return memo[node_id]

    for node_id in items:
        progress(node_id)
    return memo


def serialize_node(row, progress):
    return {key: row[key] for key in ("id", "parent_id", "kind", "title", "note", "starts_on", "ends_on", "due_on", "weight", "is_public", "is_done", "is_main", "is_week_focus", "position", "hidden_at", "created_at", "updated_at")} | {"progress": progress[row["id"]]}


@router.get("/nodes")
def list_nodes(user=Depends(require_user)):
    with connect() as db:
        rows = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=? ORDER BY position,created_at", (user["id"],))]
    scores = compute_progress(rows)
    return [serialize_node(row, scores) for row in rows]


@router.post("/nodes", status_code=201)
def create_node(data: NodeInput, user=Depends(require_user)):
    if data.kind not in PARENTS:
        raise HTTPException(422, "目标类型无效")
    values = data.model_dump()
    check_dates(values)
    with transaction() as db:
        if data.parent_id:
            parent = owned_node(db, user["id"], data.parent_id)
            if parent["kind"] != PARENTS[data.kind]:
                raise HTTPException(422, "目标层级不正确")
        elif data.kind != "vision":
            raise HTTPException(422, "请选择上级目标")
        if data.kind == "vision" and db.execute("SELECT 1 FROM nodes WHERE user_id=? AND kind='vision'", (user["id"],)).fetchone():
            raise HTTPException(409, "每位用户只能建立一个四年愿景")
        if data.kind == "year" and db.execute("SELECT COUNT(*) FROM nodes WHERE user_id=? AND kind='year'", (user["id"],)).fetchone()[0] >= 4:
            raise HTTPException(422, "四年愿景最多包含 4 个学年")
        node_id = uid()
        timestamp = iso()
        db.execute(
            "INSERT INTO nodes(id,user_id,parent_id,kind,title,note,starts_on,ends_on,due_on,weight,is_public,position,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (node_id, user["id"], data.parent_id, data.kind, data.title.strip(), data.note,
             data.starts_on, data.ends_on, data.due_on, data.weight, int(data.is_public), data.position, timestamp, timestamp),
        )
        node = dict(db.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone())
        save_version(db, node)
        add_event(db, user["id"], node_id, "created", {"title": data.title, "kind": data.kind})
    return serialize_node(node, {node_id: 0.0})


@router.patch("/nodes/{node_id}")
def update_node(node_id: str, data: NodeUpdate, user=Depends(require_user)):
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "没有需要保存的变化")
    check_dates(changes)
    with transaction() as db:
        before = owned_node(db, user["id"], node_id)
        target_kind = changes.get("kind", before["kind"])
        target_parent_id = changes.get("parent_id", before["parent_id"])
        if target_kind not in PARENTS:
            raise HTTPException(422, "目标类型无效")
        branch = [dict(row) for row in db.execute(
            "WITH RECURSIVE branch(id,kind,depth) AS ("
            "SELECT id,kind,0 FROM nodes WHERE id=? AND user_id=? "
            "UNION ALL SELECT child.id,child.kind,branch.depth+1 FROM nodes child "
            "JOIN branch ON child.parent_id=branch.id WHERE child.user_id=?"
            ") SELECT id,kind,depth FROM branch ORDER BY depth",
            (node_id, user["id"], user["id"]),
        )]
        branch_ids = {row["id"] for row in branch}
        if target_parent_id in branch_ids:
            raise HTTPException(422, "上级目标不能是自身或下级目标")
        if target_parent_id:
            parent = owned_node(db, user["id"], target_parent_id)
            if parent["kind"] != PARENTS[target_kind]:
                raise HTTPException(422, "上级目标与层级不匹配")
        elif target_kind != "vision":
            raise HTTPException(422, "请选择上级目标")
        if target_kind == "vision" and db.execute(
            "SELECT 1 FROM nodes WHERE user_id=? AND kind='vision' AND id<>?",
            (user["id"], node_id),
        ).fetchone():
            raise HTTPException(409, "每位用户只能建立一个四年愿景")
        shift = list(PARENTS).index(target_kind) - list(PARENTS).index(before["kind"])
        shifted_kinds = {}
        for row in branch:
            next_index = list(PARENTS).index(row["kind"]) + shift
            if not 0 <= next_index < len(PARENTS):
                raise HTTPException(422, "下级目标超出可用层级，请先调整下级目标")
            shifted_kinds[row["id"]] = list(PARENTS)[next_index]
        year_count = db.execute("SELECT COUNT(*) FROM nodes WHERE user_id=? AND kind='year'", (user["id"],)).fetchone()[0]
        year_count -= sum(row["kind"] == "year" for row in branch)
        year_count += sum(kind == "year" for kind in shifted_kinds.values())
        if year_count > 4:
            raise HTTPException(422, "四年愿景最多包含 4 个学年")
        if target_kind != "task":
            if changes.get("is_main"):
                raise HTTPException(422, "只有日任务能设为今日主任务")
            if before["is_main"]:
                changes["is_main"] = False
        if target_kind != "week":
            if changes.get("is_week_focus"):
                raise HTTPException(422, "只有周重点能加入周计划")
            if before["is_week_focus"]:
                changes["is_week_focus"] = False
        effective_due = changes.get("due_on", before["due_on"])
        effective_main = changes.get("is_main", bool(before["is_main"]))
        if "is_main" in changes or "due_on" in changes and before["is_main"]:
            if effective_main and (target_kind != "task" or not effective_due):
                raise HTTPException(422, "只有指定日期的任务能设为今日主任务")
            if effective_main and (not before["is_main"] or effective_due != before["due_on"]):
                count = db.execute("SELECT COUNT(*) FROM nodes WHERE user_id=? AND kind='task' AND due_on=? AND is_main=1", (user["id"], effective_due)).fetchone()[0]
                if count >= 3:
                    raise HTTPException(422, "每天最多 3 个主任务")
        effective_start = changes.get("starts_on", before["starts_on"])
        effective_focus = changes.get("is_week_focus", bool(before["is_week_focus"]))
        if "is_week_focus" in changes or "starts_on" in changes and before["is_week_focus"]:
            if effective_focus and (target_kind != "week" or not effective_start):
                raise HTTPException(422, "仅周重点可以加入周计划")
            if effective_focus and (not before["is_week_focus"] or effective_start != before["starts_on"]):
                count = db.execute("SELECT COUNT(*) FROM nodes WHERE user_id=? AND kind='week' AND starts_on=? AND is_week_focus=1", (user["id"], effective_start)).fetchone()[0]
                if count >= 5:
                    raise HTTPException(422, "每周最多 5 个重点")
        values = {**before, **changes}
        check_dates(values)
        for key in ("is_public", "is_done", "is_main", "is_week_focus"):
            if key in changes:
                changes[key] = int(changes[key])
        if "title" in changes:
            changes["title"] = changes["title"].strip()
            if not changes["title"]:
                raise HTTPException(422, "标题不能为空")
        if shift:
            for row in branch[1:]:
                next_kind = shifted_kinds[row["id"]]
                db.execute(
                    "UPDATE nodes SET kind=?,is_main=CASE WHEN ?='task' THEN is_main ELSE 0 END,"
                    "is_week_focus=CASE WHEN ?='week' THEN is_week_focus ELSE 0 END,updated_at=? WHERE id=? AND user_id=?",
                    (next_kind, next_kind, next_kind, iso(), row["id"], user["id"]),
                )
                save_version(db, owned_node(db, user["id"], row["id"]))
        columns = ",".join(f"{key}=?" for key in changes)
        db.execute(f"UPDATE nodes SET {columns},updated_at=? WHERE id=? AND user_id=?", (*changes.values(), iso(), node_id, user["id"]))
        after = owned_node(db, user["id"], node_id)
        save_version(db, after)
        event_kind = "completed" if changes.get("is_done") == 1 else "corrected" if "is_done" in changes else "updated"
        add_event(db, user["id"], node_id, event_kind, {"fields": list(changes), "title": after["title"], "shifted_descendants": len(branch)-1 if shift else 0})
        rows = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=?", (user["id"],))]
    return serialize_node(after, compute_progress(rows))


@router.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: str, user=Depends(require_user)):
    with transaction() as db:
        node = owned_node(db, user["id"], node_id)
        branch_ids = [row[0] for row in db.execute(
            "WITH RECURSIVE branch(id) AS ("
            "SELECT id FROM nodes WHERE id=? AND user_id=? "
            "UNION ALL SELECT child.id FROM nodes child JOIN branch ON child.parent_id=branch.id WHERE child.user_id=?"
            ") SELECT id FROM branch",
            (node_id, user["id"], user["id"]),
        )]
        placeholders = ",".join("?" for _ in branch_ids)
        db.execute(
            f"DELETE FROM node_versions WHERE user_id=? AND node_id IN ({placeholders})",
            (user["id"], *branch_ids),
        )
        db.execute("DELETE FROM nodes WHERE id=? AND user_id=?", (node_id, user["id"]))
        add_event(db, user["id"], None, "deleted", {"title": node["title"], "count": len(branch_ids)})


@router.get("/nodes/{node_id}/versions")
def versions(node_id: str, user=Depends(require_user)):
    with connect() as db:
        owned_node(db, user["id"], node_id)
        rows = db.execute("SELECT version,snapshot,created_at FROM node_versions WHERE user_id=? AND node_id=? ORDER BY version DESC", (user["id"], node_id)).fetchall()
    return [{"version": row["version"], "snapshot": json.loads(row["snapshot"]), "created_at": row["created_at"]} for row in rows]


@router.get("/today")
def today(day: str | None = None, user=Depends(require_user)):
    day = day or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(422, "日期无效")
    with connect() as db:
        rows = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=? AND kind='task' AND due_on=? ORDER BY is_main DESC,position,created_at", (user["id"], day))]
    return [serialize_node(row, compute_progress(rows)) for row in rows]


@router.get("/weeks/{week_start}")
def week_plan(week_start: str, user=Depends(require_user)):
    try:
        start = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(422, "日期无效")
    end = start + timedelta(days=6)
    with connect() as db:
        rows = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=? AND kind='week' AND starts_on=? ORDER BY position,created_at", (user["id"], start.isoformat()))]
        tasks = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=? AND kind='task' AND due_on BETWEEN ? AND ? ORDER BY due_on,position", (user["id"], start.isoformat(), end.isoformat()))]
    scores = compute_progress(rows + tasks)
    return {"start": start.isoformat(), "focus": [serialize_node(x, scores) for x in rows if x["is_week_focus"]], "tasks": [serialize_node(x, scores) for x in tasks]}


@router.post("/weeks/{week_start}/finalize")
def finalize_week(week_start: str, user=Depends(require_user)):
    try:
        date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(422, "日期无效")
    with transaction() as db:
        rows = db.execute("SELECT id,title FROM nodes WHERE user_id=? AND kind='week' AND starts_on=? AND is_week_focus=1", (user["id"], week_start)).fetchall()
        if not 3 <= len(rows) <= 5:
            raise HTTPException(422, "请先选出 3–5 个周重点")
        add_event(db, user["id"], None, "week_planned", {"week_start": week_start, "focus_ids": [x["id"] for x in rows]})
    return {"message": "周计划已确定", "focus_count": len(rows)}


@router.get("/events")
def events(limit: int = 100, user=Depends(require_user)):
    limit = max(1, min(limit, 500))
    with connect() as db:
        rows = db.execute("SELECT * FROM events WHERE user_id=? ORDER BY occurred_at DESC LIMIT ?", (user["id"], limit)).fetchall()
    return [{**dict(row), "detail": json.loads(row["detail"])} for row in rows]


def public_nodes(db, username):
    user = db.execute("SELECT id,username FROM users WHERE username=? AND deleted_at IS NULL", (username.lower(),)).fetchone()
    if not user:
        raise HTTPException(404, "公开主页不存在")
    rows = [dict(x) for x in db.execute("SELECT * FROM nodes WHERE user_id=? AND is_public=1 AND hidden_at IS NULL", (user["id"],))]
    visible = {x["id"] for x in rows}
    rows = [x for x in rows if x["parent_id"] is None or x["parent_id"] in visible]
    # Repeat until descendants of private ancestors have been removed.
    while True:
        allowed = {x["id"] for x in rows}
        trimmed = [x for x in rows if x["parent_id"] is None or x["parent_id"] in allowed]
        if len(trimmed) == len(rows):
            break
        rows = trimmed
    return user, rows


@router.get("/public/{username}")
def public_profile(username: str):
    with connect() as db:
        user, rows = public_nodes(db, username)
    scores = compute_progress(rows, public=True)
    safe = ("id", "parent_id", "kind", "title", "starts_on", "ends_on", "due_on", "position", "is_done")
    return {"username": user["username"], "nodes": [{key: row[key] for key in safe} | {"progress": scores[row["id"]]} for row in rows]}


class ReportInput(BaseModel):
    node_id: str
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/reports", status_code=201)
def create_report(data: ReportInput, user=Depends(require_user)):
    with transaction() as db:
        owner = db.execute("SELECT u.username FROM nodes n JOIN users u ON u.id=n.user_id WHERE n.id=?", (data.node_id,)).fetchone()
        if not owner:
            raise HTTPException(404, "公开内容不存在")
        _, visible = public_nodes(db, owner["username"])
        if data.node_id not in {node["id"] for node in visible}:
            raise HTTPException(404, "公开内容不存在")
        db.execute("INSERT INTO reports VALUES(?,?,?,?,?,?)", (uid(), user["id"], data.node_id, data.reason, "open", iso()))
    return {"message": "举报已提交"}


@router.get("/admin/reports")
def list_reports(user=Depends(require_admin)):
    with connect() as db:
        return [dict(x) for x in db.execute("SELECT * FROM reports ORDER BY created_at DESC LIMIT 100")]


@router.post("/admin/nodes/{node_id}/hide")
def hide_node(node_id: str, user=Depends(require_admin)):
    with transaction() as db:
        node = db.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        if not node:
            raise HTTPException(404, "内容不存在")
        db.execute("UPDATE nodes SET hidden_at=? WHERE id=?", (iso(), node_id))
        add_event(db, node["user_id"], node_id, "moderated", {"action": "hidden"})
        db.execute("UPDATE reports SET status='resolved' WHERE node_id=?", (node_id,))
    return {"message": "已隐藏公开内容"}
