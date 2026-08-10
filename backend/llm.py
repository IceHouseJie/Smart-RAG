"""AI 基础设施：通义千问 client / embedding / 向量库 + 查询改写。"""

import os
from openai import OpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

import config

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL")
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-v3",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    check_embedding_ctx_length=False,
)
vector_store = Chroma(
    embedding_function=embeddings,
    persist_directory=str(config.CHROMA_DIR),
)


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
