"""AI Chat service: query knowledge graph and web search."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import requests

from src.config import get_settings
from src.db import get_session, init_db
from src.repositories import EvaluationRepository, ProjectRepository, TrialRepository

logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    """Response from AI chat."""

    answer: str
    sources: list[str]
    from_graph: bool


def _build_project_context() -> str:
    """Build context from all projects in database."""
    init_db()
    session = get_session()
    project_repo = ProjectRepository(session)
    eval_repo = EvaluationRepository(session)
    trial_repo = TrialRepository(session)

    projects = project_repo.list_with_options()

    # Add AI Radar platform info
    platform_info = """## AI Radar 平台介绍

AI Radar 是一个 AI 开源项目雷达与技术吸收工作台，用于帮助团队发现、评估、试用和归档 GitHub 上的开源 AI 项目。

### 主要功能

1. **AI 助手** - 基于知识图谱的智能问答，可以查询项目信息和状态
2. **Radar** - 候选项目池，浏览、筛选、评估和认领项目
3. **Trials** - 试用管理，跟踪项目试用状态和进度
4. **Shares** - 分享归档，记录试用结论和经验
5. **Knowledge Graph** - 知识图谱，可视化项目关系

### 使用流程

1. **发现项目** - 系统自动从 GitHub Search 和 GitHub Trending 抓取项目
2. **初筛评估** - 设置项目方向标签、评估推荐分
3. **认领试用** - 团队成员认领感兴趣的项目进行试用
4. **记录结论** - 试用完成后记录结果和经验
5. **归档分享** - 将结论沉淀到知识图谱

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

        # Add evaluation info
        evaluation = eval_repo.get_latest_by_project(p.id) if p.id else None
        if evaluation:
            parts.append(f"评估状态: {evaluation.decision}")
            if evaluation.recommendation_score:
                parts.append(f"推荐分: {evaluation.recommendation_score}/5")
            if evaluation.decision_reason:
                parts.append(f"决策原因: {evaluation.decision_reason}")

        # Add trial info
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

    # Some APIs (like Minimax) return reasoning_content separately
    # We only want the main content
    content = message.get("content", "")

    # Filter out thinking blocks if they're embedded in content
    # Common patterns: <think>...</think>, <reasoning>...</reasoning>
    import re

    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    content = re.sub(r"<reasoning>.*?</reasoning>", "", content, flags=re.DOTALL)
    content = content.strip()

    return content


def _search_web(query: str) -> str:
    """Search web for GitHub projects related to query."""
    try:
        settings = get_settings()
        if not settings.llm_api_key:
            return "未配置LLM API Key，无法进行Web搜索。"

        # Use LLM to generate search suggestions
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        prompt = f"""用户询问: {query}

请推荐5个相关的GitHub开源项目，每个项目包含：
1. 项目名称和GitHub链接
2. 简短描述
3. 主要功能
4. 适用场景

请以JSON格式返回：
{{"projects": [{{"name": "...", "url": "...", "description": "...", "features": "...", "scenarios": "..."}}]}}"""

        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": "你是一个AI开源项目专家，擅长推荐相关的GitHub项目。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        resp = requests.post(
            f"{settings.llm_base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            return f"Web搜索失败: HTTP {resp.status_code}"

        content = _extract_content(resp.json())

        # Extract JSON from response
        try:
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end != -1:
                json_str = content[start:end]
                data = json.loads(json_str)
                projects = data.get("projects", [])

                if projects:
                    result_parts = ["## Web搜索结果\n"]
                    for i, proj in enumerate(projects, 1):
                        result_parts.append(f"### {i}. {proj.get('name', '未知')}")
                        if proj.get("url"):
                            result_parts.append(f"链接: {proj['url']}")
                        if proj.get("description"):
                            result_parts.append(f"描述: {proj['description']}")
                        if proj.get("features"):
                            result_parts.append(f"功能: {proj['features']}")
                        if proj.get("scenarios"):
                            result_parts.append(f"场景: {proj['scenarios']}")
                        result_parts.append("")
                    return "\n".join(result_parts)
        except json.JSONDecodeError:
            pass

        return f"## Web搜索结果\n\n{content}"

    except Exception as e:
        logger.error("Web search failed: %s", e)
        return f"Web搜索失败: {e}"


def chat_with_ai(query: str) -> ChatResponse:
    """Chat with AI about GitHub projects.

    First searches knowledge graph, then falls back to web search.
    """
    settings = get_settings()
    if not settings.llm_api_key:
        return ChatResponse(
            answer="未配置LLM API Key，请在设置中配置。",
            sources=[],
            from_graph=False,
        )

    # Build context from knowledge graph
    graph_context = _build_project_context()

    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    # First, try to answer from knowledge graph
    graph_prompt = f"""基于以下AI Radar知识图谱数据，回答用户的问题。

知识图谱数据：
{graph_context}

用户问题：{query}

请根据知识图谱中的信息回答。请注意：
1. 如果用户询问AI Radar平台本身的使用方法、功能、流程等，请根据平台介绍部分回答
2. 如果用户询问具体的GitHub项目，请根据项目信息部分回答
3. 如果用户询问项目状态（认领、试用等），请根据项目的评估和试用信息回答
4. 如果没有找到相关信息，请明确说明"知识图谱中没有找到相关项目"
5. 只有在用户明确询问新项目推荐时，才需要进行Web搜索"""

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

        graph_answer = _extract_content(resp.json())

        # Check if graph had relevant info
        has_graph_info = "没有找到" not in graph_answer and "未找到" not in graph_answer

        if has_graph_info:
            return ChatResponse(
                answer=graph_answer,
                sources=["知识图谱"],
                from_graph=True,
            )

        # Fall back to web search
        web_result = _search_web(query)

        # Combine answers
        combined_answer = f"""{graph_answer}

---

{web_result}"""

        return ChatResponse(
            answer=combined_answer,
            sources=["知识图谱", "Web搜索"],
            from_graph=False,
        )

    except Exception as e:
        logger.error("AI chat failed: %s", e)
        return ChatResponse(
            answer=f"AI请求失败: {e}",
            sources=[],
            from_graph=False,
        )
