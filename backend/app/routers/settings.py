"""Settings router: read/write application configuration."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings

router = APIRouter()


class SettingsOut(BaseModel):
    llm_api_key_set: bool
    llm_base_url: str
    llm_model: str
    github_token_set: bool


class SettingsUpdate(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    github_token: str | None = None


@router.get("", response_model=SettingsOut)
async def get_settings_endpoint(settings: Settings = Depends(get_settings)):
    return SettingsOut(
        llm_api_key_set=bool(settings.llm_api_key),
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        github_token_set=bool(settings.github_token),
    )


@router.put("")
async def update_settings(
    req: SettingsUpdate,
    settings: Settings = Depends(get_settings),
):
    env_path = settings.model_config.get("env_file")
    if not env_path:
        return {"message": "No .env file configured"}

    # Read existing
    existing: dict[str, str] = {}
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    k, _, v = stripped.partition("=")
                    existing[k.strip()] = v.strip()
    except FileNotFoundError:
        pass

    # Update
    if req.llm_api_key is not None:
        existing["LLM_API_KEY"] = req.llm_api_key.strip()
    if req.llm_base_url is not None:
        existing["LLM_BASE_URL"] = req.llm_base_url.strip()
    if req.llm_model is not None:
        existing["LLM_MODEL"] = req.llm_model.strip()
    if req.github_token is not None:
        existing["GITHUB_TOKEN"] = req.github_token.strip()

    # Write
    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")

    return {"message": "Settings saved. Restart to apply."}
