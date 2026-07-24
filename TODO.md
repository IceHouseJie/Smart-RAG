# SmartRAG — 开发计划

## 项目状态
- ✅ 工程化环境配置（Git hooks、.gitignore、.env.example）
- ✅ 项目骨架搭建（FastAPI + Streamlit 前后端联通）
- ✅ LLM 接入（通义千问，非流式）
- ⬜ 流式输出（Streaming）

---

## v1.0 MVP

### Phase 2 — 接入 LLM 核心能力
- [x] backend: 创建 `POST /chat` 接口，接收用户问题
- [x] backend: 集成通义千问 API
- [ ] backend: 实现流式输出（Streaming）
- [x] frontend: 输入框内容发到后端
- [ ] frontend: 流式显示 AI 回答
- [x] 前后端联调，跑通"提问 → AI 回答"完整链路

### Phase 3 — 文档上传与 RAG
- [ ] backend: 实现文档上传接口（PDF / TXT / MD）
- [ ] backend: 文档自动切片
- [ ] backend: LangChain + Chroma 向量化存储
- [ ] backend: 检索增强生成（RAG 问答）
- [ ] frontend: 文档上传界面
- [ ] frontend: 知识库管理（查看/删除文档）

---

## v1.1 — 体验优化
- [ ] 引用来源标注（回答中显示来自哪个文档的哪个段落）
- [ ] 多轮对话记忆（能追问，记得上下文）
- [ ] Bug 修复

## v2.0 — 功能扩展
- [ ] 多模型支持（OpenAI / 通义千问可切换）
- [ ] 对话历史管理（保存/查看历史对话）
- [ ] 支持更多文档格式

## v3.0 — 工程化
- [ ] Docker Compose 一键启动（FastAPI + Chroma + Streamlit）
- [ ] 单元测试 + API 测试
- [ ] 代码重构（Clean Code 准则）
- [ ] README 美化

---

*每个 phase 都对应一个可独立展示的里程碑。*
