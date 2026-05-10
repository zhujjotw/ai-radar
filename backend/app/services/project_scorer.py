"""Lightweight heuristic scorer: computes relevance, trialability, value, and recommendation scores."""

from __future__ import annotations

from typing import Any

from app.services.classifier import classify_project


def _star_score(stars: int) -> int:
    if stars >= 50_000:
        return 10
    if stars >= 20_000:
        return 9
    if stars >= 10_000:
        return 8
    if stars >= 5_000:
        return 7
    if stars >= 2_000:
        return 6
    if stars >= 1_000:
        return 5
    if stars >= 500:
        return 4
    if stars >= 200:
        return 3
    if stars >= 50:
        return 2
    return 1


def _fork_score(forks: int) -> int:
    if forks >= 5_000:
        return 10
    if forks >= 2_000:
        return 8
    if forks >= 1_000:
        return 7
    if forks >= 500:
        return 6
    if forks >= 200:
        return 5
    if forks >= 100:
        return 4
    if forks >= 50:
        return 3
    if forks >= 10:
        return 2
    return 1


def score_project(
    *,
    name: str = "",
    description: str = "",
    topics: list[str] | None = None,
    readme_summary: str = "",
    stars: int = 0,
    forks: int = 0,
    license: str | None = None,
    has_quickstart: bool = False,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Score a project and return all four scores plus evidence."""
    topics = topics or []

    if tags is None:
        tags = classify_project(
            name=name,
            description=description,
            topics=topics,
            readme_summary=readme_summary,
        )

    evidence_parts: list[str] = []
    num_tags = len(tags)
    if num_tags >= 3:
        relevance = 8
        evidence_parts.append(f"Matches {num_tags} domain categories")
    elif num_tags == 2:
        relevance = 7
        evidence_parts.append(f"Matches {num_tags} domain categories")
    elif num_tags == 1:
        relevance = 5
        evidence_parts.append(f"Matches {num_tags} domain category")
    else:
        relevance = 2
        evidence_parts.append("No strong domain match")

    desc_lower = (description or "").lower()
    name_lower = name.lower()
    combined_text = f"{name_lower} {desc_lower}"
    high_signal = ["agent", "llm", "rag", "inference", "mcp", "model-context"]
    for kw in high_signal:
        if kw in combined_text:
            relevance = min(10, relevance + 1)
            break

    trial = 1
    if license and license not in ("", "NOASSERTION", "NONE"):
        trial += 2
        evidence_parts.append(f"Has license ({license})")
    if has_quickstart:
        trial += 2
        evidence_parts.append("Has quickstart guide")
    if stars >= 500:
        trial += 1
    if forks >= 50:
        trial += 1
    if topics:
        trial += 1
        evidence_parts.append(f"Has {len(topics)} topics")
    trial = min(10, trial)

    value = 1
    value += min(4, _star_score(stars) // 2)
    value += min(3, _fork_score(forks) // 2)
    if num_tags >= 2:
        value += 1
    value = min(10, value)

    recommendation = round(relevance * 0.4 + trial * 0.3 + value * 0.3)

    return {
        "tags": tags,
        "relevance_score": relevance,
        "trialability_score": trial,
        "value_score": value,
        "recommendation_score": recommendation,
        "evidence": "; ".join(evidence_parts) if evidence_parts else "Minimal data",
    }


def score_project_dict(project_dict: dict[str, Any]) -> dict[str, Any]:
    """Convenience wrapper that accepts a Project-like dict."""
    return score_project(
        name=project_dict.get("name", ""),
        description=project_dict.get("description") or "",
        topics=project_dict.get("topics") or [],
        readme_summary=project_dict.get("readme_summary") or "",
        stars=project_dict.get("stars", 0),
        forks=project_dict.get("forks", 0),
        license=project_dict.get("license"),
        has_quickstart=project_dict.get("has_quickstart", False),
        tags=project_dict.get("tags"),
    )
