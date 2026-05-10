"""Auth router: login via LDAP, return JWT."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import AuthUser, authenticate_ldap, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user, token = authenticate_ldap(req.username, req.password)
    return LoginResponse(
        access_token=token,
        user={
            "username": user.username,
            "email": user.email,
            "groups": user.groups,
        },
    )


@router.get("/me")
async def me(current_user: AuthUser = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "email": current_user.email,
        "groups": current_user.groups,
    }
