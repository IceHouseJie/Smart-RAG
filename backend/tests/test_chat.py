"""/chat 端点的测试：空库短路、流式落库、404、LLM 降级、追问持久化。"""

import db
import main


def _seed_doc(app_env, source="guide.txt", content="SmartRAG 支持多种文档格式。"):
    app_env.vector_store.add_texts([content], [{"source": source}])


def test_chat_empty_kb(app_env):
    resp = app_env.client.post("/chat", json={"question": "你好"})
    assert resp.status_code == 200
    assert main.EMPTY_KB_MESSAGE in resp.text
    sid = int(resp.headers["X-Session-Id"])

    # 空库短路也落库一轮（user + assistant）
    msgs = db.get_messages(sid)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "你好"
    assert msgs[1]["content"] == main.EMPTY_KB_MESSAGE


def test_chat_with_docs_streams_answer(app_env):
    _seed_doc(app_env)
    resp = app_env.client.post("/chat", json={"question": "支持什么格式"})
    assert resp.status_code == 200
    assert app_env.llm.stream_answer in resp.text

    sid = int(resp.headers["X-Session-Id"])
    assert db.get_messages(sid)[-1]["content"] == app_env.llm.stream_answer


def test_chat_stale_session_404(app_env):
    resp = app_env.client.post("/chat", json={"question": "x", "session_id": 999})
    assert resp.status_code == 404


def test_chat_llm_fallback(app_env):
    _seed_doc(app_env)  # 有文档才走 LLM 生成路径
    app_env.llm.fail_llm = True
    resp = app_env.client.post("/chat", json={"question": "问"})
    assert main.LLM_FALLBACK_MESSAGE in resp.text

    sid = int(resp.headers["X-Session-Id"])
    # 降级文案也落库，且 user 消息仍在
    msgs = db.get_messages(sid)
    assert msgs[-1]["content"] == main.LLM_FALLBACK_MESSAGE
    assert msgs[0]["content"] == "问"


def test_chat_followup_persists_two_turns(app_env):
    resp1 = app_env.client.post("/chat", json={"question": "第一问"})
    sid = int(resp1.headers["X-Session-Id"])

    resp2 = app_env.client.post("/chat", json={"question": "第二问", "session_id": sid})
    assert resp2.status_code == 200

    msgs = db.get_messages(sid)
    assert len(msgs) == 4  # 两轮 = 4 条
    assert [m["content"] for m in msgs] == [
        "第一问",
        main.EMPTY_KB_MESSAGE,
        "第二问",
        main.EMPTY_KB_MESSAGE,
    ]
