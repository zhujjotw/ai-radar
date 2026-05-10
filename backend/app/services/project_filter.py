"""Hard filter: determines whether a project passes initial screening."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import load_yaml_config


def _load_filter_config() -> dict[str, Any]:
    """Load filters.yaml."""
    return load_yaml_config("filters.yaml")


def filter_project(
    *,
    stars: int = 0,
    last_pushed_at: datetime | None = None,
    is_archived: bool = False,
    filter_status: str = "needs_review",
    filter_reason: str | None = None,
) -> dict[str, str]:
    """Apply hard filter rules to a single project."""
    cfg = _load_filter_config()
    min_stars: int = cfg.get("github_min_stars", 200)
    max_inactive_days: int = cfg.get("github_max_inactive_days", 90)

    if filter_status == "override":
        return {"filter_status": "override", "filter_reason": filter_reason or ""}

    if is_archived:
        return {
            "filter_status": "filtered_out",
            "filter_reason": "Repository is archived",
        }

    if stars < min_stars:
        return {
            "filter_status": "filtered_out",
            "filter_reason": f"Stars {stars} below threshold {min_stars}",
        }

    if last_pushed_at is not None:
        now = datetime.now(timezone.utc)
        if last_pushed_at.tzinfo is None:
            last_pushed_at = last_pushed_at.replace(tzinfo=timezone.utc)
        days_inactive = (now - last_pushed_at).days
        if days_inactive > max_inactive_days:
            return {
                "filter_status": "filtered_out",
                "filter_reason": f"Inactive for {days_inactive} days (max {max_inactive_days})",
            }

    return {"filter_status": "needs_review", "filter_reason": None}


def filter_project_dict(project_dict: dict[str, Any]) -> dict[str, str]:
    """Convenience wrapper that accepts a Project-like dict."""
    return filter_project(
        stars=project_dict.get("stars", 0),
        last_pushed_at=project_dict.get("last_pushed_at"),
        is_archived=project_dict.get("is_archived", False),
        filter_status=project_dict.get("filter_status", "needs_review"),
        filter_reason=project_dict.get("filter_reason"),
    )
