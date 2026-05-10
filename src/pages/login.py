"""Login page: IX-Auth authentication."""

from __future__ import annotations

import streamlit as st

from src.services.ixauth import verify_with_default

# Center the login form
col1, col2, col3 = st.columns([3, 2, 3])

with col2:
    st.title("🔐 Login")
    st.caption("Sign in with your company account")

    with st.form("login_form"):
        username = st.text_input("Username", placeholder="zhang.san")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter username and password")
            else:
                try:
                    user_info = verify_with_default(username, password)
                    st.session_state["user"] = {
                        "username": user_info.username,
                        "email": user_info.email,
                        "groups": user_info.groups,
                        "access_token": user_info.access_token,
                    }
                    st.session_state["logged_in"] = True
                    st.success(f"Login successful! Welcome {user_info.username}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

    st.markdown("""
    **Instructions:**
    - Use company LDAP account to login
    - After login, you can access all AI Radar features
    """)
