"""LLM-powered project analysis: generate description and applicable scenarios."""

from __future__ import annotations

import json
import logging

import requests

from src.config import get_settings
from src.models import Project

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一个 AI 开源项目分析师。根据项目的 GitHub 信息，用中文生成：
1. **项目描述**: 简洁描述这个项目是什么、核心功能、技术特点（2-3 句话）
2. **适用场景**: 列出 3-5 个团队或企业可能使用这个项目的具体场景

严格以 JSON 格式返回，不要包含其他内容：
{"description": "...", "scenarios": "1. ...\n2. ...\n3. ..."}"""


def _build_user_prompt(project: Project) -> str:
    parts = [
        f"项目名称: {project.name}",
        f"GitHub: {project.github_url}",
    ]
    if project.description:
        parts.append(f"简介: {project.description}")
    if project.language:
        parts.append(f"语言: {project.language}")
    if project.topics:
        parts.append(f"Topics: {', '.join(project.topics)}")
    if project.tags:
        parts.append(f"方向标签: {', '.join(project.tags)}")
    if project.stars:
        parts.append(f"Stars: {project.stars:,}")
    if project.license:
        parts.append(f"License: {project.license}")
    return "\n".join(parts)


def analyze_project(project: Project) -> dict[str, str]:
    """Call LLM to generate project description and scenarios.

    Returns {"description": ..., "scenarios": ...}.
    On failure returns empty strings.
    """
    settings = get_settings()
    if not settings.llm_api_key:
        msg = "LLM API key not configured. Set LLM_API_KEY in .env"
        raise ValueError(msg)

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(project)},
        ],
        "temperature": 0.3,
        "max_tokens": 500,
    }

    try:
        resp = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("LLM API request failed: %s", exc)
        return {"description": "", "scenarios": ""}

    if resp.status_code != 200:
        logger.error("LLM API returned %s: %s", resp.status_code, resp.text[:200])
        return {"description": "", "scenarios": ""}

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Extract JSON object from response (model may output thinking before the JSON)
    json_str = _extract_json(content)

    if json_str:
        try:
            result = json.loads(json_str)
            return {
                "description": result.get("description", ""),
                "scenarios": result.get("scenarios", ""),
            }
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse LLM JSON response")
    return {"description": "", "scenarios": ""}


def _extract_json(text: str) -> str | None:
    """Extract the first JSON object {...} from text, ignoring surrounding content."""
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : i + 1]
    return None
