from fastapi import FastAPI
import uvicorn
from openai import OpenAI
import os
from dotenv import load_dotenv
from pydantic import BaseModel

app = FastAPI()
load_dotenv()
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

class ChatRequest(BaseModel):
    question: str

@app.get("/health")
async def health():
    return {"state":"ok"}

@app.post("/chat")
def chat(request: ChatRequest):
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL"),
        messages=[
            {"role": "user", "content": request.question}
        ] 
    )
    return {"answer": response.choices[0].message.content}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )