import streamlit as st
import requests

st.title("SmartRAG")

try:
    state = requests.get("http://localhost:8000/health",timeout=5)

    if state.status_code == 200:
        st.badge("Connection Successful", icon=":material/check:", color="green")

    else:
        st.badge("Connection Failed", icon=":material/close:",color="red")

except requests.exceptions.ConnectionError:
    st.badge("后端未启动,请联系管理员!", icon=":material/close:",color="red")



user_question = st.text_input("此处输入问题")

if st.button("发送"):
    st.write(user_question)