"""External trend sources for discovering AI projects.

MVP provides a placeholder interface with a simple URL-list import.
Future phases can add OSSInsight, GitHub Trending API, etc.
"""

from __future__ import annotations

import logging
import re

import requests

from src.models import Project

logger = logging.getLogger(__name__)


def import_from_url_list(urls: list[str]) -> list[Project]:
    """Import projects from a list of GitHub URLs.

    Each URL is resolved to its repo metadata via the GitHub API.
    URLs that don't match the ``https://github.com/owner/repo`` pattern
    are skipped with a warning.
    """
    projects: list[Project] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        match = re.match(r"https://github\.com/([^/]+/[^/]+)/?$", url)
        if not match:
            logger.warning("Skipping non-GitHub URL: %s", url)
            continue
        full_name = match.group(1)
        project = _fetch_repo_metadata(full_name)
        if project is not None:
            projects.append(project)
    return projects


def _fetch_repo_metadata(repo_full_name: str) -> Project | None:
    """Fetch minimal repo metadata from GitHub REST API."""
    from src.config import get_settings

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
        logger.error("Failed to fetch %s: %s", repo_full_name, exc)
        return None

    if resp.status_code != 200:
        logger.warning("Could not fetch %s: HTTP %s", repo_full_name, resp.status_code)
        return None

    data = resp.json()
    return Project(
        github_url=data["html_url"],
        repo_full_name=data["full_name"],
        name=data["name"],
        description=data.get("description"),
        pool="candidate",
        source="external",
        stars=data.get("stargazers_count", 0),
        forks=data.get("forks_count", 0),
        open_issues=data.get("open_issues_count", 0),
        language=data.get("language"),
        topics=data.get("topics", []),
        tags=[],
        license=data.get("license", {}).get("spdx_id") if data.get("license") else None,
        last_pushed_at=data.get("pushed_at"),
    )


def fetch_trending_repos() -> list[Project]:
    """Placeholder for future trending-source integration.

    MVP returns an empty list.  Future implementations can integrate
    OSSInsight, GitHub Trending, or other curated lists.
    """
    logger.info("External trending source not yet implemented — returning empty list")
    return []
