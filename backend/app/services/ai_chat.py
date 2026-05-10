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

        platform_info = """## AI Radar Platform Introduction

AI Radar is an AI open source project radar and tech absorption workbench that helps teams discover, evaluate, trial and archive open source AI projects from GitHub.

### Main Features

1. **AI Assistant** - Knowledge graph based intelligent Q&A for querying project info and status
2. **Radar** - Candidate project pool for browsing, filtering, evaluating and claiming projects
3. **Trials** - Trial management for tracking project trial status and progress
4. **Shares** - Share archive for recording trial conclusions and experiences
5. **Knowledge Graph** - Knowledge graph for visualizing project relationships

### Project Status Guide

- **needs_review** - Pending evaluation
- **watch** - Watching
- **try** - Ready to trial
- **reject** - Not relevant
- **adopt** - Adopted
- **claimed** - Claimed
- **running** - In trial
- **blocked** - Blocked
- **demo_done** - Demo completed
- **shared** - Shared

"""

        if not projects:
            return platform_info + "\nNo project data available."

        context_parts = [platform_info + "Here is the project information from AI Radar knowledge graph:\n"]

        for p in projects:
            parts = [f"## {p.name}"]
            if p.description:
                parts.append(f"Description: {p.description}")
            parts.append(f"GitHub: {p.github_url}")
            parts.append(f"Stars: {p.stars}")
            if p.language:
                parts.append(f"Language: {p.language}")
            if p.tags:
                parts.append(f"Tags: {', '.join(p.tags)}")
            if p.topics:
                parts.append(f"GitHub Topics: {', '.join(p.topics)}")
            if p.llm_description:
                parts.append(f"AI Description: {p.llm_description}")
            if p.llm_scenarios:
                parts.append(f"Use Cases: {p.llm_scenarios}")

            evaluation = eval_repo.get_latest_by_project(p.id) if p.id else None
            if evaluation:
                parts.append(f"Evaluation Status: {evaluation.decision}")
                if evaluation.recommendation_score:
                    parts.append(f"Recommendation Score: {evaluation.recommendation_score}/5")
                if evaluation.decision_reason:
                    parts.append(f"Decision Reason: {evaluation.decision_reason}")

            trials = trial_repo.list_by_project(p.id) if p.id else []
            if trials:
                active_trials = [t for t in trials if t.status not in ("dropped",)]
                if active_trials:
                    parts.append("Trial Status:")
                    for t in active_trials:
                        parts.append(f"  - Owner: {t.owner}, Status: {t.status}")
                        if t.due_date:
                            parts.append(f"    Due Date: {t.due_date}")
                        if t.result_summary:
                            parts.append(f"    Result: {t.result_summary}")

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
        yield {"event": "error", "data": {"content": "LLM API Key not configured. Please configure in settings."}}
        return

    graph_context = _build_project_context()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    graph_prompt = f"""Based on the following AI Radar knowledge graph data, answer the user's question.

Knowledge Graph Data:
{graph_context}

User Question: {query}

Please answer based on the information in the knowledge graph. Note:
1. If the user asks about AI Radar platform usage, features, flows etc., answer based on the platform introduction
2. If the user asks about specific GitHub projects, answer based on project information
3. If the user asks about project status (claiming, trials etc.), answer based on evaluation and trial info
4. If no relevant information is found, clearly state "No relevant project found in knowledge graph"
5. Only perform web search when the user explicitly asks for new project recommendations
6. When mentioning specific GitHub projects in the answer, add a marker after the project name: {{VIEW_PROJECT:project_name}}
   Example: LangChain {{VIEW_PROJECT:LangChain}} is a popular framework..."""

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "You are AI Radar's assistant, answering questions about GitHub open source projects based on the knowledge graph.",
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
                        "data": {"content": f"AI request failed: HTTP {resp.status_code} - {body.decode()[:200]}"},
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

        has_graph_info = "not found" not in full_answer.lower() and "no relevant" not in full_answer.lower()
        sources = ["Knowledge Graph"] if has_graph_info else ["Knowledge Graph"]

        yield {
            "event": "done",
            "data": {"sources": sources, "from_graph": has_graph_info},
        }

    except Exception as e:
        logger.error("AI chat streaming failed: %s", e)
        yield {"event": "error", "data": {"content": f"AI request failed: {e}"}}


def chat_with_ai(query: str, enable_web_search: bool = False) -> ChatResponse:
    """Synchronous chat for non-streaming use (e.g., internal calls)."""
    settings = get_settings()
    if not settings.llm_api_key:
        return ChatResponse(
            answer="LLM API Key not configured. Please configure in settings.",
            sources=[],
            from_graph=False,
        )

    graph_context = _build_project_context()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    graph_prompt = f"""Based on the following AI Radar knowledge graph data, answer the user's question.

Knowledge Graph Data:
{graph_context}

User Question: {query}

Please answer based on the information in the knowledge graph. When mentioning specific GitHub projects in the answer, add a marker after the project name: {{VIEW_PROJECT:project_name}}"""

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": "You are AI Radar's assistant, answering questions about GitHub open source projects based on the knowledge graph.",
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
                answer=f"AI request failed: HTTP {resp.status_code}",
                sources=[],
                from_graph=False,
            )

        answer = _extract_content(resp.json())
        has_graph_info = "not found" not in answer.lower() and "no relevant" not in answer.lower()

        return ChatResponse(
            answer=answer,
            sources=["Knowledge Graph"],
            from_graph=has_graph_info,
        )

    except Exception as e:
        logger.error("AI chat failed: %s", e)
        return ChatResponse(answer=f"AI request failed: {e}", sources=[], from_graph=False)
