import sqlite3
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import config, security
from app.db import connect
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", tmp_path / "test.db")
    import app.db as db_module
    monkeypatch.setattr(db_module, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setattr(config, "MAIL_HOST", "")
    monkeypatch.setattr(config, "APP_ORIGIN", "http://localhost:3000")
    monkeypatch.setattr(security, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("BOOTSTRAP_INVITE", "first-admin-code")
    with TestClient(app) as test_client:
        yield test_client


def make_user(client, email, username, invite):
    response = client.post("/api/auth/register", json={"email": email, "username": username, "password": "a-long-password-123", "invite_code": invite})
    assert response.status_code == 201, response.text
    token = parse_qs(urlparse(response.json()["dev_verification_url"]).fragment)["token"][0]
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/verify", json={"token": token}).status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": "a-long-password-123"}).status_code == 200


def create(client, kind, title, parent=None, **kwargs):
    response = client.post("/api/nodes", json={"kind": kind, "title": title, "parent_id": parent, **kwargs})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_auth_invites_and_rate_limit(client):
    assert client.post("/api/auth/register", json={"email":"x@example.com","username":"student","password":"a-long-password-123","invite_code":"bad"}).status_code == 400
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    invite = client.post("/api/admin/invites", json={"uses":1,"days":7}).json()["code"]
    client.post("/api/auth/logout")
    make_user(client, "student@example.com", "student", invite)
    assert client.post("/api/auth/register", json={"email":"other@example.com","username":"other","password":"a-long-password-123","invite_code":invite}).status_code == 400
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email":"student@example.com","password":"wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email":"student@example.com","password":"wrong-password"}).status_code == 429


def test_isolation_progress_public_and_history(client):
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    code = client.post("/api/admin/invites", json={}).json()["code"]
    root = create(client, "vision", "成为有创造力的人", is_public=True)
    year = create(client, "year", "大一", root, is_public=True)
    semester = create(client, "semester", "第一学期", year, is_public=True)
    month = create(client, "month", "完成作品集", semester, is_public=True)
    week = create(client, "week", "做出两个案例", month, starts_on="2026-09-28", is_public=True)
    public_task = create(client, "task", "完成第一篇案例", week, due_on="2026-09-28", weight=1, is_public=True)
    private_task = create(client, "task", "秘密任务", week, due_on="2026-09-28", weight=3, note="不能泄露")
    assert client.patch(f"/api/nodes/{public_task}", json={"is_done":True}).status_code == 200
    all_nodes = client.get("/api/nodes").json()
    assert next(x for x in all_nodes if x["id"] == week)["progress"] == 25.0
    public = client.get("/api/public/admin").json()
    assert next(x for x in public["nodes"] if x["id"] == week)["progress"] == 100.0
    assert "秘密任务" not in str(public) and "不能泄露" not in str(public)
    assert client.patch(f"/api/nodes/{public_task}", json={"is_done":False}).status_code == 200
    versions = client.get(f"/api/nodes/{public_task}/versions").json()
    assert len(versions) == 3
    assert any(x["kind"] == "corrected" for x in client.get("/api/events").json())
    client.post("/api/auth/logout")
    make_user(client, "student@example.com", "student", code)
    assert client.patch(f"/api/nodes/{public_task}", json={"title":"stolen"}).status_code == 404
    assert client.get(f"/api/nodes/{public_task}/versions").status_code == 404
    assert client.get("/api/nodes").json() == []


def test_move_reclassify_and_delete_goal_branch(client):
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    vision = create(client, "vision", "四年愿景")
    first_year = create(client, "year", "大一", vision)
    second_year = create(client, "year", "大二", vision)
    semester = create(client, "semester", "第一学期", first_year)
    month = create(client, "month", "旧层级", semester)
    week = create(client, "week", "旧周", month)
    task = create(client, "task", "旧任务", week)

    assert client.patch(f"/api/nodes/{semester}", json={"parent_id": second_year}).status_code == 200
    assert client.patch(f"/api/nodes/{month}", json={"kind": "semester", "parent_id": second_year}).status_code == 200
    nodes = {node["id"]: node for node in client.get("/api/nodes").json()}
    assert nodes[semester]["parent_id"] == second_year
    assert [nodes[node_id]["kind"] for node_id in (month, week, task)] == ["semester", "month", "week"]
    assert client.patch(f"/api/nodes/{month}", json={"kind": "month", "parent_id": task}).status_code == 422
    assert len(client.get(f"/api/nodes/{week}/versions").json()) == 2

    assert client.delete(f"/api/nodes/{month}").status_code == 204
    remaining = {node["id"] for node in client.get("/api/nodes").json()}
    assert remaining == {vision, first_year, second_year, semester}
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM node_versions WHERE node_id IN (?,?,?)", (month, week, task)).fetchone()[0] == 0
    assert any(event["kind"] == "deleted" for event in client.get("/api/events").json())


def test_main_limit_reports_and_hide(client):
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    root = create(client, "vision", "我的公开愿景", is_public=True)
    year = create(client, "year", "大一", root, is_public=True)
    semester = create(client, "semester", "上学期", year, is_public=True)
    month = create(client, "month", "九月", semester, is_public=True)
    week = create(client, "week", "本周", month, is_public=True)
    tasks = [create(client, "task", f"任务 {i}", week, due_on="2026-09-28", is_public=True) for i in range(4)]
    for node_id in tasks[:3]:
        assert client.patch(f"/api/nodes/{node_id}",json={"is_main":True}).status_code == 200
    assert client.patch(f"/api/nodes/{tasks[3]}",json={"is_main":True}).status_code == 422
    assert client.post("/api/reports",json={"node_id":tasks[0],"reason":"不合适的公开内容"}).status_code == 201
    assert len(client.get("/api/admin/reports").json()) == 1
    assert client.post(f"/api/admin/nodes/{tasks[0]}/hide").status_code == 200
    assert tasks[0] not in [x["id"] for x in client.get("/api/public/admin").json()["nodes"]]


def test_encrypted_key_and_empty_ai_response(client, monkeypatch):
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    root = create(client, "vision", "学会设计")
    assert client.put("/api/ai/key", json={"api_key":"sk-example-secret-value"}).status_code == 200
    with connect() as db:
        stored = db.execute("SELECT ciphertext FROM ai_keys").fetchone()[0]
    assert "sk-example" not in stored

    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":""}}]}
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return FakeResponse()
    monkeypatch.setattr("app.ai.httpx.Client", FakeClient)
    response = client.post("/api/ai/suggest",json={"action":"decompose","node_ids":[root]})
    assert response.status_code == 502
    assert client.get("/api/ai/usage").json()["used"] == 1
    assert client.delete("/api/ai/key").status_code == 204
    assert client.get("/api/ai/key").json()["configured"] is False


def test_public_child_requires_public_ancestors(client):
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    root = create(client, "vision", "公开愿景", is_public=True)
    private_year = create(client, "year", "私有学年", root)
    hidden_child = create(client, "semester", "不应公开的学期", private_year, is_public=True)
    public = client.get("/api/public/admin").json()
    assert [node["title"] for node in public["nodes"]] == ["公开愿景"]
    assert client.post("/api/reports", json={"node_id":hidden_child,"reason":"这项内容不应出现"}).status_code == 404


def test_backup_can_restore(client, tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    make_user(client, "admin@example.com", "admin", "first-admin-code")
    root = create(client, "vision", "需要备份的目标")
    backup_dir = tmp_path / "backups"
    env = {**os.environ, "DATABASE_PATH": str(tmp_path / "test.db"), "BACKUP_DIR": str(backup_dir)}
    output = subprocess.check_output([sys.executable, "scripts/backup.py"], env=env, text=True).strip()
    with sqlite3.connect(output) as restored:
        assert restored.execute("SELECT title FROM nodes WHERE id=?", (root,)).fetchone()[0] == "需要备份的目标"


def test_resend_verification_is_throttled(client):
    registration = client.post("/api/auth/register", json={"email":"admin@example.com","username":"admin","password":"a-long-password-123","invite_code":"first-admin-code"})
    assert registration.status_code == 201
    first = client.post("/api/auth/resend-verification", json={"email":"admin@example.com"})
    assert first.status_code == 200 and "dev_verification_url" not in first.json()
    with connect() as db:
        assert db.execute("SELECT COUNT(*) FROM verification_tokens").fetchone()[0] == 1
        db.execute("UPDATE verification_tokens SET expires_at=?", (security.iso(security.now() + timedelta(hours=23)),))
    second = client.post("/api/auth/resend-verification", json={"email":"admin@example.com"})
    assert second.status_code == 200 and "dev_verification_url" in second.json()
