import streamlit as st
import requests

st.title("SmartRAG")

if "messages" not in st.session_state:
    st.session_state.messages = []

try:
    state = requests.get("http://localhost:8000/health",timeout=5)

    if state.status_code == 200:
        st.badge("系统连接成功", icon=":material/check:", color="green")

    else:
        st.badge("系统连接失败", icon=":material/close:",color="red")

except requests.exceptions.ConnectionError:
    st.badge("后端未启动,请联系管理员!", icon=":material/close:",color="red")

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
        json={"question": user_question},
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