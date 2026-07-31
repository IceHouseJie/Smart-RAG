import streamlit as st
import requests

with st.sidebar:
    st.title("SmartRAG")
    try:
        state = requests.get("http://localhost:8000/health",timeout=5)

        if state.status_code == 200:
            st.badge("系统连接成功", icon=":material/check:", color="green")

        else:
            st.badge("系统连接失败", icon=":material/close:",color="red")

    except requests.exceptions.ConnectionError:
        st.badge("后端未启动,请联系管理员!", icon=":material/close:",color="red")

    upload_file = st.file_uploader("上传文档", type=["txt"])

    if upload_file is not None:
        files = {"file": (upload_file.name, upload_file.getvalue(), "text/plain")}
        resp = requests.post("http://localhost:8000/upload", files=files)
        if resp.status_code == 200:
            result = resp.json()
            st.toast(f"上传成功: {result['filename']}({result['chunks']}个片段) ")
        else:
            st.toast("上传失败")

    st.divider()
    st.subheader("已上传的文档")
    resp = requests.get("http://localhost:8000/documents")
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
                        requests.delete(f"http://localhost:8000/documents/{doc}")
                        st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_doc" in st.session_state:
    if st.button("返回聊天"):
        del st.session_state.selected_doc
        st.rerun()
    st.markdown(f"## {st.session_state.selected_doc}")
    resp = requests.get(f"http://localhost:8000/documents/{st.session_state.selected_doc}")
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
    with st.spinner("思考中..."):
        response = requests.post(
        "http://localhost:8000/chat",
        json={"question": user_question, "history": st.session_state.messages[:-1]},
        stream=True,
        timeout=30
        )
    if response.status_code == 200:
        def stream_text():
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    yield chunk.decode("utf-8")
        with st.chat_message("assistant"):
            full_response = st.write_stream(stream_text())
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    else:
        st.error("请求失败")