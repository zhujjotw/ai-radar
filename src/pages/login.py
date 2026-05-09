"""Login page: IX-Auth authentication."""

from __future__ import annotations

import streamlit as st

from src.services.ixauth import verify_with_default

# Center the login form
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.title("🔐 登录")
    st.caption("使用公司账号登录 AI Radar")

    with st.form("login_form"):
        username = st.text_input("用户名", placeholder="zhang.san")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("请输入用户名和密码")
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
                    st.success(f"登录成功！欢迎 {user_info.username}")
                    st.rerun()
                except Exception as e:
                    st.error(f"登录失败: {e}")

    st.markdown("""
    **说明：**
    - 使用公司 LDAP 账号登录
    - 登录后可访问 AI Radar 所有功能
    """)
