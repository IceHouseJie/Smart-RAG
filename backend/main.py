"""FastAPI 应用：路由层。逻辑分散在 config / db / parsers / llm 模块。"""

import os
import uvicorn
from pathlib import Path
from zipfile import BadZipFile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf.errors import PdfReadError

import config
import db
import parsers
import llm

app = FastAPI()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    question: str
    session_id: int | None = None


EMPTY_KB_MESSAGE = "知识库中暂未检索到相关内容，请先上传相关文档后再提问。"
LLM_FALLBACK_MESSAGE = "AI 服务暂时不可用，请稍后重试。"


def _make_title(question: str) -> str:
    return question.strip()[:20]


def _extract_document_text(filename: str, content: bytes) -> str:
    """提取文档文本；PDF 无文字层（扫描件）时回退视觉模型。"""
    text = parsers.extract_text(filename, content)
    if text.strip():
        return text
    if Path(filename).suffix.lower() == ".pdf":
        return llm.vision_extract_text(parsers.render_pdf_pages(content))
    return text


db.init_db()  # 启动时建表（幂等）


@app.get("/health")
async def health():
    return {"state": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    session_id = request.session_id
    if session_id is not None and db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session_id is None:
        session_id = db.create_session(_make_title(request.question))

    # 数据库是历史唯一数据源；当前问题在本次结束时才落库
    history = [ChatMessage(role=m["role"], content=m["content"])
               for m in db.get_messages(session_id)]

    def generate():
        answer_parts = []
        search_query = llm.rewrite_query(request.question, history)
        docs = llm.vector_store.similarity_search(search_query, k=3)
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
                stream = llm.client.chat.completions.create(
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
            db.insert_turn(session_id, request.question, "".join(answer_parts))

    response = StreamingResponse(generate(), media_type="text/plain")
    response.headers["X-Session-Id"] = str(session_id)
    return response


@app.get("/sessions")
def list_sessions_api():
    return {"sessions": [dict(s) for s in db.list_sessions()]}


@app.get("/sessions/{session_id}")
def get_session_api(session_id: int):
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "id": session["id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "messages": [dict(m) for m in db.get_messages(session_id)],
    }


@app.delete("/sessions/{session_id}")
def delete_session_api(session_id: int):
    if not db.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "deleted", "id": session_id}


@app.post("/upload")
async def upload_doc(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        return {"error": "文件内容为空", "status": "empty"}

    filename = os.path.basename(file.filename)
    if not parsers.is_allowed_extension(filename):
        return {"error": f"不支持的文件格式，仅支持 {'/'.join(sorted(parsers.ALLOWED_EXTENSIONS))}", "status": "error"}

    # 先提取文本再落盘：校验先于副作用，坏文件不残留
    try:
        text = _extract_document_text(filename, content)
    except (UnicodeDecodeError, PdfReadError, BadZipFile, KeyError):
        return {"error": "程序读取文档失败，请检查文件是否损坏或已加密。", "status": "error"}

    if not text.strip():
        return {"error": "未能从文档中提取到文本（图片型 PDF / 扫描件需 OCR，暂不支持）", "status": "error"}

    os.makedirs(config.DATA_DIR, exist_ok=True)
    file_path = config.DATA_DIR / filename
    with open(file_path, "wb") as f:
        f.write(content)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)

    # 先删该文件的旧向量，再加新向量（幂等：同名文件重复上传不叠加）
    llm.vector_store.delete(where={"source": filename})
    llm.vector_store.add_texts(
        texts=chunks,
        metadatas=[{"source": filename} for _ in chunks]
    )

    return {"filename": filename, "chunks": len(chunks), "status": "upload"}


@app.get("/documents")
def list_documents():
    if not config.DATA_DIR.exists():
        return {"documents": []}
    # 只暴露上传的文档，避免 conversations.db 等运行时文件被文档管理接口读到/删除
    return {"documents": [f for f in os.listdir(config.DATA_DIR) if parsers.is_allowed_extension(f)]}


@app.get("/documents/{filename}")
def get_document(filename: str):
    if not parsers.is_allowed_extension(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = config.DATA_DIR / filename
    if not file_path.exists():
        return {"error": "文件不存在"}
    try:
        with open(file_path, "rb") as f:
            text = _extract_document_text(filename, f.read())
    except (UnicodeDecodeError, PdfReadError, BadZipFile, KeyError):
        return {"error": "文档读取失败，请删除后重新上传"}
    return {"filename": filename, "content": text}


@app.delete("/documents/{filename}")
def delete_document(filename: str):
    if not parsers.is_allowed_extension(filename):
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = config.DATA_DIR / filename
    if file_path.exists():
        file_path.unlink()

    llm.vector_store.delete(where={"source": filename})

    return {"status": "delete", "filename": filename}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
