# SmartRAG — 智能知识库问答系统

## 项目概述
基于 RAG（检索增强生成）的私有知识库问答系统。上传文档 → 自动构建向量知识库 → 自然语言提问 → AI 基于私有内容回答。

## 技术栈
- **后端**: FastAPI + Uvicorn + Pydantic
- **AI**: LangChain + Chroma + LLM API（OpenAI / 通义千问）
- **前端**: Streamlit
- **部署**: Docker + Docker Compose

## 版本规划
- **v1.0** — MVP：核心 RAG 问答链路跑通
- **v1.1** — 体验优化：引用来源、多轮对话
- **v2.0** — 扩展：多模型、对话历史
- **v3.0** — 工程化：Docker、测试、重构

## 教学约定
用户是"借助 AI 和官方文档使用技术栈"的阶段，目标是达到实习水平。所有代码任务遵循引导式教学：解释 Why > 给出 How > 用户自己动手。参见 [[session-log-001]]。

## 必须使用的技能 (Skills)

在编写、审查或重构任何代码之前，**必须先依次调用以下两个技能**：

1. **`andrej-karpathy-skills:karpathy-guidelines`** — Karpathy 的行为准则，用于避免常见的 LLM 编码失误（过度复杂化、缺乏验证标准等）
2. **`clean-code`** — 遵循 Robert C. Martin 的 Clean Code 原则，确保代码整洁、可读、可维护

### 使用方式

在执行任何代码相关的任务时，按以下顺序调用：

```
Skill: andrej-karpathy-skills:karpathy-guidelines
Skill: clean-code
```

### 为何需要这两个技能

- **Karpathy 准则** 帮助避免过度工程化、明确成功标准、做精准的手术式修改
- **Clean Code** 确保代码命名清晰、函数短小、职责单一、测试优先

两者互补，共同保证代码质量和开发效率。
