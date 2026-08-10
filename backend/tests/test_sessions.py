"""/sessions 端点与 SQLite DAO 的测试（用临时 DB）。"""

import db


def test_list_sessions_empty(app_env):
    resp = app_env.client.get("/sessions")
    assert resp.json() == {"sessions": []}


def test_create_and_get_session(app_env):
    sid = db.create_session("测试会话")
    resp = app_env.client.get(f"/sessions/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == sid
    assert data["title"] == "测试会话"
    assert data["messages"] == []


def test_get_session_404(app_env):
    resp = app_env.client.get("/sessions/999")
    assert resp.status_code == 404


def test_delete_session_cascades_messages(app_env):
    sid = db.create_session("测试会话")
    db.insert_turn(sid, "你好", "世界")
    assert db.get_messages(sid)  # 删之前有消息

    resp = app_env.client.delete(f"/sessions/{sid}")
    assert resp.json()["status"] == "deleted"
    assert db.get_session(sid) is None
    assert db.get_messages(sid) == []  # 级联删消息


def test_delete_session_404(app_env):
    resp = app_env.client.delete("/sessions/999")
    assert resp.status_code == 404
