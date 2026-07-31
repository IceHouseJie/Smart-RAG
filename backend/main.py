from fastapi import FastAPI, UploadFile, File  
import uvicorn  
from openai import OpenAI  
import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

app = FastAPI()
load_dotenv()
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

class ChatRequest(BaseModel):
    question: str
    history: list = Field(default_factory=list)

embeddings = OpenAIEmbeddings(
    model = "text-embedding-v3",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    check_embedding_ctx_length=False
)
vector_store = Chroma(
    embedding_function=embeddings,
    persist_directory="chroma_db"
)

@app.get("/health")
async def health():
    return {"state":"ok"}

def rewrite_query(question: str, history: list) -> str:
    """根据对话历史，把用户问题改写成自包含的检索问题。无历史时原样返回。"""
    if not history:
        return question

    history_text = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in history]
    )
    resp = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=[
            {"role": "system", "content": "你是检索查询改写助手。根据对话历史，把用户的新问题改写成独立、完整的检索问题，使其不依赖历史也能直接检索到相关内容。只输出改写后的问题，不要任何解释。"},
            {"role": "user", "content": f"历史对话：\n{history_text}\n\n新问题：{question}\n\n改写后的问题："}
        ]
    )
    return resp.choices[0].message.content.strip()

@app.post("/chat")
def chat(request: ChatRequest):
    def generate():
        search_query = rewrite_query(request.question, request.history)
        docs = vector_store.similarity_search(search_query, k=3)
        if not docs:
            yield "知识库中暂未检索到相关内容，请先上传相关文档后再提问。"
            return
        context = "\n\n".join([doc.page_content for doc in docs])
        messages = [
            {"role": "system", "content": f"请基于以下文档内容回答问题: \n{context}"}
        ]
        messages.extend(request.history)
        messages.append({"role": "user", "content": request.question})
        stream = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=messages,
            stream=True
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    return StreamingResponse(generate(), media_type="text/plain")

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
    file_path = f"data/{filename}"
    with open(file_path,"wb") as f:
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
    if not os.path.exists("data"):
        return {"documents": []}
    files = os.listdir("data")
    return {"documents": files}

@app.get("/documents/{filename}")
def get_document(filename: str):
    file_path = os.path.join("data", filename)
    if not os.path.exists(file_path):
        return {"error": "文件不存在"}
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"filename": filename, "content": content}

@app.delete("/documents/{filename}")
def delete_document(filename: str):
    file_path = os.path.join("data", filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    vector_store.delete(where={"source": filename})

    return {"status": "delete", "filename": filename}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )