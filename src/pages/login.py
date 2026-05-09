"""Login page: IX-Auth authentication."""

from __future__ import annotations

import streamlit as st

from src.services.ixauth import verify_with_default

# Center the login form
col1, col2, col3 = st.columns([3, 2, 3])

with col2:
    # Logo and title
    st.markdown(
        """
    <div style="text-align: center; margin-bottom: 2rem;">
        <div style="font-size: 4rem;">🔭</div>
        <h1 style="color: #58a6ff; margin: 0.5rem 0;">AI Radar</h1>
        <p style="color: #8b949e; font-size: 1.1rem;">AI 开源项目雷达与技术吸收工作台</p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        st.markdown(
            """
        <div style="text-align: center; margin-bottom: 1rem;">
            <h3 style="color: #c9d1d9;">🔐 登录</h3>
            <p style="color: #8b949e; font-size: 0.9rem;">使用公司账号登录</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

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

    # Info section
    st.markdown(
        """
    <div style="margin-top: 2rem; padding: 1rem; background-color: #161b22; border-radius: 8px; border: 1px solid #30363d;">
        <h4 style="color: #58a6ff; margin-top: 0;">📋 说明</h4>
        <ul style="color: #8b949e; margin-bottom: 0; padding-left: 1.5rem;">
            <li>使用公司 LDAP 账号登录</li>
            <li>登录后可访问 AI Radar 所有功能</li>
            <li>数据每5小时自动更新一次</li>
        </ul>
    </div>
    """,
        unsafe_allow_html=True,
    )
