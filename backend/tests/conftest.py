"""测试共享设施：假对象 + app_env fixture。

原理：backend/main.py 的所有状态都是模块级全局变量（DB_PATH / DATA_DIR /
vector_store / client），且都在调用时解析。测试用 monkeypatch 换掉它们即可，
不依赖真实 Chroma、DashScope 网络请求或 data/ 真数据。
"""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

# 让 tests 能 import main（backend 在上级目录），并给假 env 兜底（不依赖 .env）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault("DASHSCOPE_BASE_URL", "https://test.example/v1")
os.environ.setdefault("LLM_MODEL", "test-model")

import main
import config
import db
import llm


class FakeVectorStore:
    """内存版向量库，替代真实 Chroma：记录 add/delete，similarity_search 返回已加片段。"""

    def __init__(self):
        self.sources = {}  # source -> list[chunk]

    def add_texts(self, texts, metadatas):
        for text, meta in zip(texts, metadatas):
            self.sources.setdefault(meta["source"], []).append(text)

    def delete(self, where):
        self.sources.pop(where["source"], None)

    def similarity_search(self, query, k=3):
        docs = []
        for chunks in self.sources.values():
            docs.extend(SimpleNamespace(page_content=c) for c in chunks)
        return docs[:k]


class FakeCompletions:
    """模拟 client.chat.completions.create 的返回结构。"""

    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        if self._owner.fail_llm:
            raise RuntimeError("LLM 服务故障")
        if kwargs.get("stream"):
            content = self._owner.stream_answer
            chunk = SimpleNamespace(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
            )
            return iter([chunk])
        # 非流式：查询改写用
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._owner.rewrite_answer))]
        )


class FakeClient:
    """模拟 OpenAI client：查询改写（非流式）+ 回答（流式），均可配置。"""

    def __init__(self):
        self.rewrite_answer = "改写后的问题"
        self.stream_answer = "这是测试回答"
        self.fail_llm = False

    @property
    def chat(self):
        return SimpleNamespace(completions=FakeCompletions(self))


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    """把后端隔离到临时 DB / data 目录 + 假向量库 + 假 LLM，返回 TestClient 等。"""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(llm, "vector_store", FakeVectorStore())
    monkeypatch.setattr(llm, "client", FakeClient())
    db.init_db()  # 在临时 DB 建表
    return SimpleNamespace(
        client=TestClient(main.app),
        vector_store=llm.vector_store,
        llm=llm.client,
        data_dir=config.DATA_DIR,
    )
