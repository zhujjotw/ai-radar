"""Settings page: manage LLM configuration, GitHub token, and other settings."""

from __future__ import annotations

import streamlit as st

from src.config import get_settings, ROOT_DIR

# --- Load settings ---
_settings = get_settings()

# --- Page header ---
st.title("Settings")
st.caption("Configure LLM, GitHub, and other application settings")

# --- LLM Configuration ---
st.header("LLM 配置")
st.caption("用于 AI 分析项目描述和适用场景")

llm_api_key = st.text_input(
    "API Key",
    value=_settings.llm_api_key or "",
    type="password",
    key="settings_llm_api_key",
    help="OpenAI API Key 或兼容的 API Key",
)
llm_base_url = st.text_input(
    "Base URL",
    value=_settings.llm_base_url,
    key="settings_llm_base_url",
    help="API 端点，默认 OpenAI",
)
llm_model = st.text_input(
    "Model",
    value=_settings.llm_model,
    key="settings_llm_model",
    help="模型名称，如 gpt-4o-mini",
)

# Show current config status
if _settings.llm_api_key:
    st.success(f"✅ LLM 已配置: {_settings.llm_model} @ {_settings.llm_base_url}")
else:
    st.warning("⚠️ LLM 未配置，AI 分析功能不可用")

if st.button("保存 LLM 配置", key="save_llm_config"):
    env_path = _settings.model_config.get("env_file")
    if env_path:
        existing = {}
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _, v = stripped.partition("=")
                        existing[k.strip()] = v.strip()
        except FileNotFoundError:
            pass

        existing["LLM_API_KEY"] = llm_api_key.strip()
        existing["LLM_BASE_URL"] = llm_base_url.strip()
        existing["LLM_MODEL"] = llm_model.strip()

        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        st.success("✅ LLM 配置已保存到 .env，下次启动生效")
        st.rerun()

st.divider()

# --- GitHub Configuration ---
st.header("GitHub 配置")
st.caption("用于 GitHub API 请求，避免速率限制")

github_token = st.text_input(
    "GitHub Token",
    value=_settings.github_token or "",
    type="password",
    key="settings_github_token",
    help="Personal access token (可选，但推荐配置以避免速率限制)",
)

if _settings.github_token:
    st.success("✅ GitHub Token 已配置")
else:
    st.info("ℹ️ 未配置 GitHub Token，API 请求有速率限制")

if st.button("保存 GitHub 配置", key="save_github_config"):
    env_path = _settings.model_config.get("env_file")
    if env_path:
        existing = {}
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and "=" in stripped:
                        k, _, v = stripped.partition("=")
                        existing[k.strip()] = v.strip()
        except FileNotFoundError:
            pass

        existing["GITHUB_TOKEN"] = github_token.strip()

        with open(env_path, "w", encoding="utf-8") as f:
            for k, v in existing.items():
                f.write(f"{k}={v}\n")

        st.success("✅ GitHub 配置已保存到 .env，下次启动生效")
        st.rerun()

st.divider()

# --- Current Configuration Display ---
st.header("当前配置")
st.caption("只读，显示当前生效的配置")

col1, col2 = st.columns(2)

with col1:
    st.subheader("LLM")
    st.code(f"""
Model: {_settings.llm_model}
Base URL: {_settings.llm_base_url}
API Key: {"***" if _settings.llm_api_key else "Not set"}
    """)

with col2:
    st.subheader("GitHub")
    st.code(f"""
Token: {"***" if _settings.github_token else "Not set"}
    """)

st.divider()

# --- Configuration Help ---
st.header("配置帮助")

with st.expander("如何获取 API Key？"):
    st.markdown("""
    **OpenAI API Key:**
    1. 访问 https://platform.openai.com/api-keys
    2. 创建新的 API Key
    3. 复制并粘贴到上方

    **兼容 API (如 DeepSeek, Moonshot):**
    1. 获取对应平台的 API Key
    2. 修改 Base URL 为平台提供的端点
    3. 填入 API Key
    """)

with st.expander("如何获取 GitHub Token？"):
    st.markdown("""
    1. 访问 https://github.com/settings/tokens
    2. 点击 "Generate new token (classic)"
    3. 选择权限：`public_repo` (读取公开仓库)
    4. 生成并复制 Token
    """)

with st.expander("配置文件位置"):
    st.code(f"""
配置文件: {ROOT_DIR / ".env"}
    """)
