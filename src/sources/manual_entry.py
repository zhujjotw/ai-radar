"""Manual project entry — create a Project from a user-supplied GitHub URL.

Fetches repo metadata from the GitHub API and allows the caller to attach
an optional ``override_reason`` when bypassing filter rules.
"""

from __future__ import annotations

import logging
import re

import requests

from src.config import get_settings
from src.models import Project

logger = logging.getLogger(__name__)

_GITHUB_REPO_PATTERN = re.compile(r"https://github\.com/([^/]+/[^/]+)/?$")


def create_project_from_url(
    github_url: str,
    *,
    override_reason: str | None = None,
    tags: list[str] | None = None,
) -> Project:
    """Create a ``Project`` from a GitHub URL by fetching repo metadata.

    Parameters
    ----------
    github_url:
        Full GitHub repository URL (``https://github.com/owner/repo``).
    override_reason:
        Optional reason to bypass hard-filter rules.
    tags:
        Optional direction tags to attach to the project.

    Returns
    -------
    Project
        An unsaved ``Project`` model instance.

    Raises
    ------
    ValueError
        If the URL does not match the expected GitHub format.
    """
    match = _GITHUB_REPO_PATTERN.match(github_url.strip())
    if not match:
        msg = f"Invalid GitHub URL: {github_url}"
        raise ValueError(msg)

    full_name = match.group(1)
    data = _fetch_repo_data(full_name)

    project = Project(
        github_url=data.get("html_url", github_url),
        repo_full_name=data.get("full_name", full_name),
        name=data.get("name", full_name.split("/", 1)[-1]),
        description=data.get("description"),
        pool="candidate",
        source="manual",
        discovered_reason=override_reason,
        stars=data.get("stargazers_count", 0),
        forks=data.get("forks_count", 0),
        open_issues=data.get("open_issues_count", 0),
        language=data.get("language"),
        topics=data.get("topics", []),
        tags=tags or [],
        license=data.get("license", {}).get("spdx_id") if data.get("license") else None,
        last_pushed_at=data.get("pushed_at"),
        filter_status="needs_review",
        filter_reason=override_reason,
    )

    if override_reason:
        project.filter_status = "override"

    return project


def _fetch_repo_data(repo_full_name: str) -> dict:
    """Fetch repository metadata from GitHub REST API.

    Returns an empty dict on failure so callers can still create a
    minimal ``Project``.
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = get_settings().github_token
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"https://api.github.com/repos/{repo_full_name}",
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Failed to fetch repo data for %s: %s", repo_full_name, exc)
        return {}

    if resp.status_code != 200:
        logger.warning("Could not fetch %s: HTTP %s", repo_full_name, resp.status_code)
        return {}

    return resp.json()
