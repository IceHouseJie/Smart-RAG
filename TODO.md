# SmartRAG — 开发计划

## 项目状态
- ✅ 工程化环境配置（Git hooks、.gitignore、.env.example）
- ✅ 项目骨架搭建（FastAPI + Streamlit 前后端联通）
- ✅ LLM 接入（通义千问，流式输出）
- ✅ 文档上传与 RAG 问答

---

## v1.0 MVP ✅

### Phase 2 — 接入 LLM 核心能力
- [x] backend: 创建 `POST /chat` 接口，接收用户问题
- [x] backend: 集成通义千问 API
- [x] backend: 实现流式输出（Streaming）
- [x] frontend: 输入框内容发到后端
- [x] frontend: 流式显示 AI 回答
- [x] 前后端联调，跑通"提问 → AI 回答"完整链路

### Phase 3 — 文档上传与 RAG
- [x] backend: 实现文档上传接口（TXT）
- [x] backend: 文档自动切片（RecursiveCharacterTextSplitter）
- [x] backend: LangChain + Chroma 向量化存储
- [x] backend: 检索增强生成（RAG 问答）
- [x] frontend: 文档上传界面（侧边栏）
- [x] backend: 文档列表 / 内容预览端点
- [x] backend: 删除文档端点（删文件 + 删向量）
- [x] frontend: 知识库管理（查看/删除文档）

### 代码清理
- [x] 删除无用 import（shutil）
- [x] 删除 debug print
- [x] 优化逐字符 yield 为整段输出
- [x] 增加文档上传异常处理（空文件 / 二进制文件）

### 前端交互优化
- [x] 回车发送替代按钮点击
- [x] 聊天气泡展示（用户 + AI）
- [x] 对话历史留存（session_state）
- [x] 侧边栏 + 主区域布局改造（含欢迎页 / 文档预览三态切换）

---

## v1.1 — 体验优化
- [ ] 引用来源标注（回答中显示来自哪个文档的哪个段落）
- [x] 多轮对话记忆（能追问，记得上下文）
- [ ] Bug 修复

## v2.0 — 功能扩展
- [ ] 多模型支持（OpenAI / 通义千问可切换）
- [ ] 对话历史管理（保存/查看历史对话）
- [ ] 支持更多文档格式（PDF、Markdown）

## v3.0 — 工程化
- [ ] Docker Compose 一键启动（FastAPI + Chroma + Streamlit）
- [ ] 单元测试 + API 测试
- [ ] 代码重构（Clean Code 准则）
- [ ] README 美化

---

*每个 phase 都对应一个可独立展示的里程碑。*
