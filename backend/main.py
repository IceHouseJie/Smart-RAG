import sqlite3
from contextlib import closing
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
from openai import OpenAI
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal
from fastapi.responses import StreamingResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"

app = FastAPI()
load_dotenv(BASE_DIR / ".env")
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    question: str
    session_id: int | None = None

embeddings = OpenAIEmbeddings(
    model = "text-embedding-v3",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    check_embedding_ctx_length=False
)
vector_store = Chroma(
    embedding_function=embeddings,
    persist_directory=str(CHROMA_DIR)
)

# ---------- 对话历史持久化（SQLite） ----------
DB_PATH = DATA_DIR / "conversations.db"

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
    DATA_DIR.mkdir(exist_ok=True)
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

init_db()

@app.get("/health")
async def health():
    return {"state":"ok"}

EMPTY_KB_MESSAGE = "知识库中暂未检索到相关内容，请先上传相关文档后再提问。"
LLM_FALLBACK_MESSAGE = "AI 服务暂时不可用，请稍后重试。"

def _make_title(question: str) -> str:
    return question.strip()[:20]

def rewrite_query(question: str, history: list) -> str:
    """根据对话历史，把用户问题改写成自包含的检索问题。无历史时原样返回。"""
    if not history:
        return question

    history_text = "\n".join(
        [f"{msg.role}: {msg.content}" for msg in history]
    )
    try:
        resp = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {"role": "system", "content": "你是检索查询改写助手。根据对话历史，把用户的新问题改写成独立、完整的检索问题，使其不依赖历史也能直接检索到相关内容。只输出改写后的问题，不要任何解释。"},
                {"role": "user", "content": f"历史对话：\n{history_text}\n\n新问题：{question}\n\n改写后的问题："}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        # 改写失败时降级为原始问题，保证主链路不中断
        return question

@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id is not None and get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session_id is None:
        session_id = create_session(_make_title(request.question))

    # 数据库是历史唯一数据源；当前问题在本次结束时才落库
    history = [ChatMessage(role=m["role"], content=m["content"])
               for m in get_messages(session_id)]

    def generate():
        answer_parts = []
        search_query = rewrite_query(request.question, history)
        docs = vector_store.similarity_search(search_query, k=3)
        if not docs:
            answer_parts.append(EMPTY_KB_MESSAGE)
            yield EMPTY_KB_MESSAGE
        else:
            context = "\n\n".join([doc.page_content for doc in docs])
            messages = [
                {"role": "system", "content": f"请基于以下文档内容回答问题: \n{context}"}
            ]
            messages.extend([msg.model_dump() for msg in history])
            messages.append({"role": "user", "content": request.question})
            try:
                stream = client.chat.completions.create(
                    model=os.getenv("LLM_MODEL"),
                    messages=messages,
                    stream=True
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        answer_parts.append(chunk.choices[0].delta.content)
                        yield chunk.choices[0].delta.content
            except Exception:
                answer_parts.append(LLM_FALLBACK_MESSAGE)
                yield LLM_FALLBACK_MESSAGE

        # 放生成器末尾而非 finally：客户端中途断开会抛 GeneratorExit，跳过落库
        if answer_parts:
            insert_turn(session_id, request.question, "".join(answer_parts))

    response = StreamingResponse(generate(), media_type="text/plain")
    response.headers["X-Session-Id"] = str(session_id)
    return response

@app.get("/sessions")
def list_sessions_api():
    return {"sessions": [dict(s) for s in list_sessions()]}

@app.get("/sessions/{session_id}")
def get_session_api(session_id: int):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": session["id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "messages": [dict(m) for m in get_messages(session_id)],
    }

@app.delete("/sessions/{session_id}")
def delete_session_api(session_id: int):
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "deleted", "id": session_id}

@app.post("/upload")
async def upload_doc(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        return {"error": "文件内容为空", "status": "empty"}

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "程序读取文档失败,请上传正确格式的文档.", "status": "error"}

    filename = os.path.basename(file.filename)
    file_path = DATA_DIR / filename
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(content)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500,chunk_overlap=50)
    chunks = splitter.split_text(text)

    # 先删该文件的旧向量，再加新向量（幂等：同名文件重复上传不叠加）
    vector_store.delete(where={"source": filename})
    vector_store.add_texts(
        texts=chunks,
        metadatas=[{"source": filename} for _ in chunks]
    )

    return {"filename": filename, "chunks": len(chunks), "status": "upload"}

@app.get("/documents")
def list_documents():
    if not DATA_DIR.exists():
        return {"documents": []}
    # 只暴露上传的 txt，避免 conversations.db 等运行时文件被文档管理接口读到/删除
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".txt")]
    return {"documents": files}

@app.get("/documents/{filename}")
def get_document(filename: str):
    if not filename.endswith(".txt"):
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = DATA_DIR / filename
    if not file_path.exists():
        return {"error": "文件不存在"}
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": filename, "content": content}

@app.delete("/documents/{filename}")
def delete_document(filename: str):
    if not filename.endswith(".txt"):
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = DATA_DIR / filename
    if file_path.exists():
        file_path.unlink()

    vector_store.delete(where={"source": filename})

    return {"status": "delete", "filename": filename}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )