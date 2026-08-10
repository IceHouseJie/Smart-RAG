"""对话历史持久化（SQLite）：sessions/messages 两表 + 数据访问层。"""

import sqlite3
from contextlib import closing

import config

DB_PATH = config.DATA_DIR / "conversations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id);
"""


def _connect() -> sqlite3.Connection:
    """每操作开新连接：FastAPI 同步端点跑线程池，共享连接会触发 check_same_thread 错误。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # 默认 OFF，不设则删会话不级联删消息
    return conn


def init_db():
    config.DATA_DIR.mkdir(exist_ok=True)
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)


def create_session(title: str) -> int:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("INSERT INTO sessions (title) VALUES (?)", (title,))
        return cur.lastrowid


def get_session(session_id: int) -> sqlite3.Row | None:
    with closing(_connect()) as conn:
        return conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()


def list_sessions() -> list:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC, id DESC"
        ).fetchall()


def get_messages(session_id: int) -> list:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()


def delete_session(session_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return cur.rowcount > 0


def insert_turn(session_id: int, user_content: str, assistant_content: str):
    """一个事务写入一轮（user + assistant）并刷新会话时间，保证 all-or-nothing。"""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)",
            (session_id, user_content),
        )
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, 'assistant', ?)",
            (session_id, assistant_content),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = datetime('now','localtime') WHERE id = ?",
            (session_id,),
        )
