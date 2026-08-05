import streamlit as st
import requests

API = "http://localhost:8000"


def _load_session(session_id: int):
    """把指定会话的消息加载进当前展示状态。"""
    resp = requests.get(f"{API}/sessions/{session_id}")
    if resp.status_code == 200:
        data = resp.json()
        st.session_state.current_session_id = session_id
        st.session_state.messages = data["messages"]
    else:
        # 会话已被删：重置为新对话
        st.session_state.current_session_id = None
        st.session_state.messages = []
    st.rerun()


def _delete_session(session_id: int):
    requests.delete(f"{API}/sessions/{session_id}")
    if st.session_state.get("current_session_id") == session_id:
        st.session_state.current_session_id = None
        st.session_state.messages = []
    st.rerun()


def _new_chat():
    st.session_state.current_session_id = None
    st.session_state.messages = []
    st.rerun()


with st.sidebar:
    st.title("SmartRAG")
    try:
        state = requests.get(f"{API}/health", timeout=5)

        if state.status_code == 200:
            st.badge("系统连接成功", icon=":material/check:", color="green")

        else:
            st.badge("系统连接失败", icon=":material/close:", color="red")

    except requests.exceptions.ConnectionError:
        st.badge("后端未启动,请联系管理员!", icon=":material/close:", color="red")

    upload_file = st.file_uploader("上传文档", type=["txt"])

    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = set()

    if upload_file is not None and upload_file.name not in st.session_state.uploaded_files:
        files = {"file": (upload_file.name, upload_file.getvalue(), "text/plain")}
        resp = requests.post(f"{API}/upload", files=files)
        if resp.status_code == 200:
            result = resp.json()
            st.session_state.uploaded_files.add(upload_file.name)
            st.toast(f"上传成功: {result['filename']}({result['chunks']}个片段) ")
        else:
            st.toast("上传失败")

    st.divider()
    st.subheader("已上传的文档")
    resp = requests.get(f"{API}/documents")
    if resp.status_code == 200:
        docs = resp.json().get("documents", [])
        if docs:
            for doc in docs:
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(f"{doc}", key=f"view_{doc}"):
                        st.session_state.selected_doc = doc
                with col2:
                    if st.button("🗑️", key=f"del_{doc}"):
                        requests.delete(f"{API}/documents/{doc}")
                        st.session_state.uploaded_files.discard(doc)
                        st.rerun()

    st.divider()
    st.subheader("对话历史")
    if st.button("＋ 新对话", use_container_width=True):
        _new_chat()
    sessions = requests.get(f"{API}/sessions").json().get("sessions", [])
    for s in sessions:
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(f"{s['title']}  {s['updated_at'][5:16]}", key=f"load_{s['id']}", use_container_width=True):
                _load_session(s["id"])
        with col2:
            if st.button("🗑️", key=f"del_sess_{s['id']}"):
                _delete_session(s["id"])


if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_doc" in st.session_state:
    if st.button("返回聊天"):
        del st.session_state.selected_doc
        st.rerun()
    st.markdown(f"## {st.session_state.selected_doc}")
    resp = requests.get(f"{API}/documents/{st.session_state.selected_doc}")
    if resp.status_code == 200:
        data = resp.json()
        st.text(data.get("content", ""))

elif not st.session_state.messages:
    st.markdown("""
    ## 欢迎使用 SmartRAG 🧠

    **SmartRAG** 是一个基于 RAG 的私有知识库问答系统。

    ### 使用步骤
    1. 📄 **左侧侧边栏**上传文档
    2. 💬 在下方输入问题
    3. 🤖 AI 将基于你的知识库回答

    ---
    *支持格式：TXT*
    """)
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

user_question = st.chat_input("此处输入问题")


if user_question:
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)

    payload = {"question": user_question}
    if st.session_state.current_session_id is not None:
        payload["session_id"] = st.session_state.current_session_id

    with st.spinner("思考中..."):
        response = requests.post(
            f"{API}/chat",
            json=payload,
            stream=True,
            timeout=60
        )

    if response.status_code == 404:
        # 后端会话已被删：重置为新对话
        st.session_state.current_session_id = None
        st.session_state.messages = []
        st.rerun()
    elif response.status_code != 200:
        st.error("请求失败")
    else:
        def stream_text():
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    yield chunk.decode("utf-8")
        try:
            with st.chat_message("assistant"):
                full_response = st.write_stream(stream_text())
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            session_id = response.headers.get("X-Session-Id")
            if session_id:
                st.session_state.current_session_id = int(session_id)
            st.rerun()  # 刷新侧边栏会话列表，首问后新会话立即出现
        except Exception:
            st.error("网络中断或 AI 服务异常，请重试")
