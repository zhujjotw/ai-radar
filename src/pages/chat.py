"""AI Chat page: query knowledge graph about GitHub projects."""

from __future__ import annotations

import streamlit as st

from src.services.ai_chat import chat_with_ai

# --- Page header ---
st.title("AI 助手")
st.caption("基于知识图谱的GitHub项目检索")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize web search toggle
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = False

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input with web search toggle
col1, col2 = st.columns([4, 1])

with col1:
    prompt = st.chat_input("询问关于GitHub项目的问题...")

with col2:
    st.write("")  # Spacer
    st.write("")  # Spacer
    web_search = st.toggle(
        "Web搜索",
        value=st.session_state.web_search_enabled,
        help="开启后，当知识图谱中没有相关信息时会进行Web搜索",
    )
    st.session_state.web_search_enabled = web_search

if prompt:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("正在检索知识图谱..."):
            response = chat_with_ai(prompt, enable_web_search=st.session_state.web_search_enabled)

            # Display answer
            st.markdown(response.answer)

            # Display sources
            if response.sources:
                st.caption(f"来源: {', '.join(response.sources)}")

    # Add assistant message to chat history
    st.session_state.messages.append({"role": "assistant", "content": response.answer})

# Sidebar with example queries
with st.sidebar:
    st.header("设置")

    # Web search toggle in sidebar
    web_search_sidebar = st.toggle(
        "启用Web搜索",
        value=st.session_state.web_search_enabled,
        help="开启后，当知识图谱中没有相关信息时会进行Web搜索",
        key="web_search_sidebar",
    )
    st.session_state.web_search_enabled = web_search_sidebar

    st.divider()

    st.header("示例查询")
    st.markdown("""
    **项目检索：**
    - Agent框架有哪些项目？
    - 推荐一些RAG相关的项目
    - 有哪些LLM评测工具？
    - 向量数据库有哪些选择？
    - 有没有好用的AI代码助手？

    **项目状态：**
    - 当前有哪些认领项目？
    - 哪些项目正在试用中？
    - 有哪些项目已完成demo？
    - 谁在负责项目试用？
    - 当前有哪些blocked项目？

    **平台使用：**
    - AI Radar怎么使用？
    - 项目状态有哪些？
    - 怎么认领项目？
    """)

    if st.button("清空对话"):
        st.session_state.messages = []
        st.rerun()
