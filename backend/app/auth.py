"""JWT authentication: create/verify tokens, FastAPI dependency."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings, get_settings
from app.services.ixauth import verify_with_default

security = HTTPBearer()

ALGORITHM = "HS256"


@dataclass
class AuthUser:
    username: str
    email: str
    groups: list[str]


def create_access_token(user: AuthUser, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user.username,
        "email": user.email,
        "groups": user.groups,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str, secret: str) -> AuthUser:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return AuthUser(
            username=payload["sub"],
            email=payload.get("email", ""),
            groups=payload.get("groups", []),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def authenticate_ldap(username: str, password: str) -> tuple[AuthUser, str]:
    """Authenticate via LDAP and return (user, jwt_token)."""
    try:
        info = verify_with_default(username, password)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e

    settings = get_settings()
    user = AuthUser(
        username=info.username,
        email=info.email,
        groups=info.groups,
    )
    token = create_access_token(user, settings)
    return user, token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    """FastAPI dependency: extract and validate JWT from Authorization header."""
    return decode_token(credentials.credentials, settings.jwt_secret)
