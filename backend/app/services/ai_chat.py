"""AI Chat service: query knowledge graph and web search with streaming support."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.db import Session, engine, init_db
from app.repositories import EvaluationRepository, ProjectRepository, TrialRepository

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    answer: str
    sources: list[str]
    from_graph: bool


def _build_project_context() -> str:
    """Build context from all projects in database."""
    init_db()
    with Session(engine) as session:
        project_repo = ProjectRepository(session)
        eval_repo = EvaluationRepository(session)
        trial_repo = TrialRepository(session)

        projects = project_repo.list_with_options()

        platform_info = """## AI Radar 平台介绍

AI Radar 是一个 AI 开源项目雷达与技术吸收工作台，用于帮助团队发现、评估、试用和归档 GitHub 上的开源 AI 项目。

### 主要功能

1. **AI 助手** - 基于知识图谱的智能问答，可以查询项目信息和状态
2. **Radar** - 候选项目池，浏览、筛选、评估和认领项目
3. **Trials** - 试用管理，跟踪项目试用状态和进度
4. **Shares** - 分享归档，记录试用结论和经验
5. **Knowledge Graph** - 知识图谱，可视化项目关系

### 项目状态说明

- **needs_review** - 待评估
- **watch** - 关注中
- **try** - 可试用
- **reject** - 不相关
- **adopt** - 已采纳
- **claimed** - 已认领
- **running** - 试用中
- **blocked** - 阻塞
- **demo_done** - 演示完成
- **shared** - 已分享

"""

        if not projects:
            return platform_info + "\n暂无项目数据。"

        context_parts = [platform_info + "以下是AI Radar知识图谱中的项目信息：\n"]

        for p in projects:
            parts = [f"## {p.name}"]
            if p.description:
                parts.append(f"描述: {p.description}")
            parts.append(f"GitHub: {p.github_url}")
            parts.append(f"Stars: {p.stars}")
            if p.language:
                parts.append(f"语言: {p.language}")
            if p.tags:
                parts.append(f"方向标签: {', '.join(p.tags)}")
            if p.topics:
                parts.append(f"GitHub Topics: {', '.join(p.topics)}")
            if p.llm_description:
                parts.append(f"AI描述: {p.llm_description}")
            if p.llm_scenarios:
                parts.append(f"适用场景: {p.llm_scenarios}")

            evaluation = eval_repo.get_latest_by_project(p.id) if p.id else None
            if evaluation:
                parts.append(f"评估状态: {evaluation.decision}")
                if evaluation.recommendation_score:
                    parts.append(f"推荐分: {evaluation.recommendation_score}/5")
                if evaluation.decision_reason:
                    parts.append(f"决策原因: {evaluation.decision_reason}")

            trials = trial_repo.list_by_project(p.id) if p.id else []
            if trials:
                active_trials = [t for t in trials if t.status not in ("dropped",)]
                if active_trials:
                    parts.append("试用状态:")
                    for t in active_trials:
                        parts.append(f"  - 负责人: {t.owner}, 状态: {t.status}")
                        if t.due_date:
                            parts.append(f"    截止日期: {t.due_date}")
                        if t.result_summary:
                            parts.append(f"    结果: {t.result_summary}")

            context_parts.append("\n".join(parts))

        return "\n\n---\n\n".join(context_parts)


def _extract_content(resp_data: dict) -> str:
    """Extract content from LLM response, filtering out thinking/reasoning."""
    choices = resp_data.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")

    content = re.sub(r"჉.*?つ", "", content, flags=re.DOTALL)
    content = re.sub(r"<reasoning>.*?</reasoning>", "", content, flags=re.DOTALL)
    return content.strip()


def _extract_chunk_content(chunk_data: dict) -> str:
    """Extract content from a streaming chunk."""
    choices = chunk_data.get("choices", [])
    if not choices:
        return ""
    delta = choices[0].get("delta", {})
    return delta.get("content", "")


async def stream_chat(
    query: str,
    enable_web_search: bool = False,
) -> AsyncGenerator[dict, None]:
    """Stream chat response as SSE-compatible dicts.

    Yields: {"event": "chunk", "data": {"content": "..."}}
    Finally: {"event": "done", "data": {"sources": [...], "from_graph": bool}}
    """
    settings = get_settings()
    if not settings.llm_api_key:
        yield {"event": "error", "data": {"content": "未配置LLM API Key，请在设置中配置。"}}
        return

    graph_context = _build_project_context()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    graph_prompt = f"""基于以下AI Radar知识图谱数据，回答用户的问题。

知识图谱数据：
{graph_context}

用户问题：{query}

请根据知识图谱中的信息回答。请注意：
1. 如果用户询问AI Radar平台本身的使用方法、功能、流程等，请根据平台介绍部分回答
2. 如果用户询问具体的GitHub项目，请根据项目信息部分回答
3. 如果用户询问项目状态（认领、试用等），请根据项目的评估和试用信息回答
4. 如果没有找到相关信息，请明确说明"知识图谱中没有找到相关项目"
5. 只有在用户明确询问新项目推荐时，才需要进行Web搜索
6. 当回答中提到具体的GitHub项目时，请在项目名称后添加标记：{{VIEW_PROJECT:项目名称}}
   例如：LangChain {{VIEW_PROJECT:LangChain}} 是一个流行的框架..."""

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "你是AI Radar的助手，基于知识图谱回答关于GitHub开源项目的问题。",
            },
            {"role": "user", "content": graph_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
        "stream": True,
    }

    full_answer = ""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream(
                "POST",
                f"{settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    yield {
                        "event": "error",
                        "data": {"content": f"AI请求失败: HTTP {resp.status_code} - {body.decode()[:200]}"},
                    }
                    return

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        content = _extract_chunk_content(chunk)
                        if content:
                            full_answer += content
                            yield {"event": "chunk", "data": {"content": content}}
                    except json.JSONDecodeError:
                        continue

        has_graph_info = "没有找到" not in full_answer and "未找到" not in full_answer
        sources = ["知识图谱"] if has_graph_info else ["知识图谱"]

        yield {
            "event": "done",
            "data": {"sources": sources, "from_graph": has_graph_info},
        }

    except Exception as e:
        logger.error("AI chat streaming failed: %s", e)
        yield {"event": "error", "data": {"content": f"AI请求失败: {e}"}}


def chat_with_ai(query: str, enable_web_search: bool = False) -> ChatResponse:
    """Synchronous chat for non-streaming use (e.g., internal calls)."""
    settings = get_settings()
    if not settings.llm_api_key:
        return ChatResponse(
            answer="未配置LLM API Key，请在设置中配置。",
            sources=[],
            from_graph=False,
        )

    graph_context = _build_project_context()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    graph_prompt = f"""基于以下AI Radar知识图谱数据，回答用户的问题。

知识图谱数据：
{graph_context}

用户问题：{query}

请根据知识图谱中的信息回答。当回答中提到具体的GitHub项目时，请在项目名称后添加标记：{{VIEW_PROJECT:项目名称}}"""

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "你是AI Radar的助手，基于知识图谱回答关于GitHub开源项目的问题。",
            },
            {"role": "user", "content": graph_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    try:
        import requests

        resp = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            return ChatResponse(
                answer=f"AI请求失败: HTTP {resp.status_code}",
                sources=[],
                from_graph=False,
            )

        answer = _extract_content(resp.json())
        has_graph_info = "没有找到" not in answer and "未找到" not in answer

        return ChatResponse(
            answer=answer,
            sources=["知识图谱"],
            from_graph=has_graph_info,
        )

    except Exception as e:
        logger.error("AI chat failed: %s", e)
        return ChatResponse(answer=f"AI请求失败: {e}", sources=[], from_graph=False)
