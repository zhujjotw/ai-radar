"""Direction classifier: maps project metadata to domain tags.

Uses keywords.yaml to classify projects into categories like
Agent, RAG, Eval, Inference, Workflow, Developer Tooling, MCP.
"""

from __future__ import annotations

import re
from typing import Any

from src.config import load_yaml_config


def _normalize(text: str) -> str:
    """Lowercase and strip non-alphanumeric chars for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _load_keyword_map() -> dict[str, list[str]]:
    """Load keywords.yaml and normalize keywords for matching."""
    raw: dict[str, Any] = load_yaml_config("keywords.yaml")
    result: dict[str, list[str]] = {}
    for category, keywords in raw.items():
        if isinstance(keywords, list):
            result[category] = [_normalize(k) for k in keywords if isinstance(k, str)]
    return result


def classify_project(
    *,
    name: str = "",
    description: str = "",
    topics: list[str] | None = None,
    readme_summary: str = "",
) -> list[str]:
    """Return a sorted list of matching direction tags for a project.

    Matching strategy: normalize both keywords and corpus text, then
    check for substring containment.  A category matches if *any* of
    its keywords appears in the concatenated text.
    """
    topics = topics or []
    corpus_parts = [name, description, readme_summary] + list(topics)
    corpus = _normalize(" ".join(corpus_parts))

    if not corpus:
        return []

    keyword_map = _load_keyword_map()
    tags: list[str] = []
    for category, keywords in keyword_map.items():
        for kw in keywords:
            if kw and kw in corpus:
                tags.append(category)
                break

    return sorted(set(tags))


def classify_project_dict(project_dict: dict[str, Any]) -> list[str]:
    """Convenience wrapper that accepts a Project-like dict."""
    return classify_project(
        name=project_dict.get("name", ""),
        description=project_dict.get("description") or "",
        topics=project_dict.get("topics") or [],
        readme_summary=project_dict.get("readme_summary") or "",
    )
