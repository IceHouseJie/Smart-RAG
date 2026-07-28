from fastapi import FastAPI, UploadFile, File  
import uvicorn  
from openai import OpenAI  
import os
from dotenv import load_dotenv
from pydantic import BaseModel
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

@app.post("/chat")
def chat(request: ChatRequest):
    def generate():
        docs = vector_store.similarity_search(request.question, k=3)
        context = "\n\n".join([doc.page_content for doc in docs])
        stream = client.chat.completions.create(
            model=os.getenv("LLM_MODEL"),
            messages=[
                {"role": "system", "content": f"请基于以下文档内容回答问题: \n{context}"},
                {"role": "user", "content": request.question}
            ],
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

    file_path = f"data/{file.filename}"
    with open(file_path,"wb") as f:
        f.write(content)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500,chunk_overlap=50)
    chunks = splitter.split_text(text)

    vector_store.add_texts(
        texts=chunks,
        metadatas=[{"source": file.filename} for _ in chunks]
    )

    return {"filename": file.filename, "chunks": len(chunks), "status": "upload"}

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