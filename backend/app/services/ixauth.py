"""IX-Auth client: verify username/password and get JWT token."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Default IX-Auth URL
DEFAULT_AUTH_URL = "http://10.113.3.11:31822"


@dataclass
class UserInfo:
    """User info from IX-Auth verify response."""

    username: str
    email: str
    groups: list[str]
    access_token: str
    refresh_token: str
    access_expire: int


def verify(auth_url: str, username: str, password: str) -> UserInfo:
    """Call IX-Auth /verify to authenticate user."""
    resp = requests.post(
        f"{auth_url}/verify",
        json={"username": username, "password": password},
        timeout=10,
    )

    # Handle password error (returns HTTP 500 with plain text)
    if resp.status_code == 500:
        raise Exception("密码错误")

    resp.raise_for_status()
    data = resp.json()

    # Check code: 0 means success
    if data.get("code") != 0:
        raise Exception(f"认证失败: {data.get('message', '未知错误')}")

    user_data = data["data"]
    return UserInfo(
        username=user_data["username"],
        email=user_data.get("email", ""),
        groups=user_data.get("group", []),
        access_token=user_data["accessToken"],
        refresh_token=user_data["refreshToken"],
        access_expire=user_data.get("accessExpire", 0),
    )


def verify_with_default(username: str, password: str) -> UserInfo:
    """Verify using default IX-Auth URL."""
    return verify(DEFAULT_AUTH_URL, username, password)
