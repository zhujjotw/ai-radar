"""AI Chat page: query knowledge graph about GitHub projects."""

from __future__ import annotations

import re

import streamlit as st

from src.services.ai_chat import chat_with_ai


def _render_answer(answer: str) -> None:
    """Render answer with project view buttons."""
    # Pattern to match {VIEW_PROJECT:project_name}
    pattern = r"\{VIEW_PROJECT:([^}]+)\}"
    
    # Split answer by the pattern
    parts = re.split(pattern, answer)
    
    # Process parts
    i = 0
    while i < len(parts):
        if i % 2 == 0:
            # Regular text
            if parts[i].strip():
                st.markdown(parts[i])
        else:
            # Project name - render button
            project_name = parts[i].strip()
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{project_name}**")
            with col2:
                if st.button("View Details", key=f"view_{project_name}_{i}"):
                    st.query_params["project"] = project_name
                    st.switch_page("pages/radar.py")
        i += 1


# --- Page header ---
st.title("AI Assistant")
st.caption("GitHub project search based on knowledge graph")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize web search toggle
if "web_search_enabled" not in st.session_state:
    st.session_state.web_search_enabled = False

# Display chat history
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            _render_answer(message["content"])
        else:
            st.markdown(message["content"])

# Sidebar with settings
with st.sidebar:
    st.header("Settings")

    # Web search toggle in sidebar
    web_search_sidebar = st.toggle(
        "Enable Web Search",
        value=st.session_state.web_search_enabled,
        help="When enabled, performs web search when knowledge graph has no relevant info",
        key="web_search_sidebar",
    )
    st.session_state.web_search_enabled = web_search_sidebar

# Chat input at the bottom
prompt = st.chat_input("Ask about GitHub projects...")

if prompt:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Searching knowledge graph..."):
            response = chat_with_ai(prompt, enable_web_search=st.session_state.web_search_enabled)

            # Display answer with project buttons
            _render_answer(response.answer)

            # Display sources
            if response.sources:
                st.caption(f"Sources: {', '.join(response.sources)}")

    # Add assistant message to chat history
    st.session_state.messages.append({"role": "assistant", "content": response.answer})
