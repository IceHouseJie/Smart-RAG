# SmartRAG — 智能知识库问答系统

基于 **RAG（检索增强生成）** 的私有知识库问答系统：上传文档 → 向量化建库 → 自然语言提问 → AI 基于你的私有内容回答。

## ✨ 功能特性

- 📄 **多格式文档**：TXT / Markdown / PDF / DOCX
- 👁️ **扫描件识别**：图片型 PDF 走视觉模型（qwen-vl）看图提取内容，图表 / 版式也能理解
- 🔍 **RAG 问答**：文档切片向量化，检索增强，回答基于知识库内容而非自由发挥
- 💬 **多轮对话**：上下文记忆 + 查询改写，可自然追问
- 🗂️ **对话历史管理**：SQLite 持久化，会话保存 / 查看 / 删除
- 🛡️ **健壮性**：空知识库短路、LLM 降级、断网友好提示、幂等上传、路径穿越防护
- 🐳 **一键部署**：Docker Compose 双容器

## 🏗️ 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + Uvicorn + Pydantic |
| AI | LangChain + Chroma + OpenAI SDK（通义千问 DashScope 兼容接口）+ qwen-vl 视觉模型 |
| 文档解析 | pypdf（PDF）+ python-docx（DOCX）+ pymupdf（扫描件渲染） |
| 存储 | SQLite（对话历史）+ Chroma（向量库） |
| 前端 | Streamlit |
| 部署 | Docker Compose |

## 🚀 快速开始

### 方式一：本地运行

```bash
# 1. 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env   # 填入你的 DASHSCOPE_API_KEY

# 3. 启动后端（端口 8000）
cd backend && ../.venv/bin/python main.py

# 4. 另开终端，启动前端（端口 8501）
cd frontend && ../.venv/bin/streamlit run app.py
```

浏览器打开 <http://localhost:8501> 即可使用。

### 方式二：Docker 一键启动

```bash
docker compose up -d
# 前端 http://localhost:8501 ｜ 后端 http://localhost:8000
# 停止：docker compose down（data/chroma 卷会保留数据）
```

> 需要先配置 `.env`（compose 会读取它注入容器）。首次构建需联网拉取基础镜像与依赖。

### 运行测试

```bash
cd backend && ../.venv/bin/python -m pytest tests/ -v   # 34 个用例
```

## ⚙️ 环境变量（`.env`）

| 变量 | 说明 |
|---|---|
| `DASHSCOPE_API_KEY` | 通义千问 DashScope API Key（必填） |
| `DASHSCOPE_BASE_URL` | DashScope 兼容接口地址 |
| `LLM_MODEL` | 模型名（如 `qwen-plus`） |
| `VISION_MODEL` | 扫描件视觉模型（如 `qwen-vl-plus`） |

> 前端 `API_BASE_URL`：本地开发默认 `http://localhost:8000`；Docker 里由 compose 设为 `http://backend:8000`，无需手动配置。

## 📁 项目结构

```
backend/
  main.py      FastAPI 路由层
  config.py    路径与环境配置
  db.py        SQLite 对话历史（sessions/messages）
  parsers.py   文档解析（txt/md/pdf/docx + 扫描件渲染）
  llm.py       AI 基础设施（client / 向量库 / 查询改写 / 视觉识别）
  tests/       pytest 测试（34 用例）
frontend/
  app.py       Streamlit 界面
Dockerfile          多阶段构建（backend / frontend 双 target）
docker-compose.yml  双容器编排 + 数据卷
requirements.txt
```

## 📌 开发进度

- ✅ **v1.0** — RAG 问答全链路跑通
- ✅ **v1.1** — 多轮记忆、查询改写、Bug 修复与前端实测
- ✅ **v2.0** — 对话历史管理 + 多文档格式（PDF / Markdown / DOCX）
- ✅ **v3.0** — 单元测试（34 用例）、代码重构（五模块）、Docker 部署
- ✅ **附加** — 扫描件 PDF 识别（视觉模型 qwen-vl）
