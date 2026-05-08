"""GitHub Search integration for discovering candidate AI projects.

Uses the GitHub REST API v3 ``/search/repositories`` endpoint to find
repositories matching the keywords defined in ``config/keywords.yaml``.
"""

from __future__ import annotations

import logging
import re
import time
import requests

from src.config import get_settings, load_yaml_config
from src.models import Project

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_PER_PAGE = 30  # GitHub max per page for search


def _build_search_query(keywords: list[str], min_stars: int = 200) -> str:
    """Build a GitHub search query from keyword list.

    Combines keywords with OR and adds a minimum-star qualifier.
    """
    keyword_part = " ".join(f'"{kw}" in:name,description,topics' for kw in keywords)
    return f"({keyword_part}) stars:>={min_stars} sort:stars"


def _parse_repo_full_name(url: str) -> str:
    """Extract ``owner/repo`` from a GitHub URL."""
    match = re.match(r"https://github\.com/([^/]+/[^/]+)/?", url)
    if not match:
        msg = f"Cannot parse repo full name from URL: {url}"
        raise ValueError(msg)
    return match.group(1)


def _fetch_search_results(
    query: str,
    *,
    token: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    """Execute a GitHub search query and return raw JSON items.

    Respects rate limits by sleeping briefly between requests.
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    items: list[dict] = []
    page = 1
    pages_needed = (max_results + _PER_PAGE - 1) // _PER_PAGE

    while page <= pages_needed:
        params = {"q": query, "per_page": _PER_PAGE, "page": page}
        try:
            resp = requests.get(
                f"{_GITHUB_API}/search/repositories",
                headers=headers,
                params=params,
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.error("GitHub API request failed: %s", exc)
            break

        if resp.status_code == 403:
            logger.warning("GitHub API rate limit hit — stopping search")
            break
        if resp.status_code != 200:
            logger.error("GitHub API returned status %s: %s", resp.status_code, resp.text[:200])
            break

        data = resp.json()
        page_items = data.get("items", [])
        items.extend(page_items)
        if len(page_items) < _PER_PAGE:
            break

        page += 1
        # Be kind to the API
        time.sleep(1)

    return items[:max_results]


def _github_item_to_project(item: dict) -> Project:
    """Convert a GitHub search API item to a ``Project`` model instance."""
    full_name = item["full_name"]
    return Project(
        github_url=item["html_url"],
        repo_full_name=full_name,
        name=item["name"],
        description=item.get("description"),
        pool="candidate",
        source="github_search",
        discovered_reason=item.get("description", "")[:200] if item.get("description") else None,
        stars=item.get("stargazers_count", 0),
        forks=item.get("forks_count", 0),
        open_issues=item.get("open_issues_count", 0),
        language=item.get("language"),
        topics=item.get("topics", []),
        tags=[],
        license=item.get("license", {}).get("spdx_id") if item.get("license") else None,
        has_quickstart=False,
        readme_summary=None,
        last_pushed_at=item.get("pushed_at"),
        last_checked_at=None,
    )


def _fetch_readme_summary(
    repo_full_name: str,
    *,
    token: str | None = None,
    max_chars: int = 500,
) -> str | None:
    """Fetch the first *max_chars* of a repo's README for summary.

    Returns ``None`` if the README cannot be fetched.
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github.raw"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"{_GITHUB_API}/repos/{repo_full_name}/readme",
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.debug("Failed to fetch README for %s: %s", repo_full_name, exc)
        return None

    if resp.status_code != 200:
        return None

    text = resp.text[:max_chars]
    return text


def search_candidate_projects(
    *,
    max_results_per_category: int = 5,
    total_max: int = 30,
    enrich_readme: bool = False,
) -> list[Project]:
    """Search GitHub for candidate AI projects across all keyword categories.

    Reads ``config/keywords.yaml`` for keyword groups, runs one search per
    group, deduplicates by ``repo_full_name``, and returns ``Project``
    instances.
    """
    settings = get_settings()
    token = settings.github_token

    keywords_config = load_yaml_config("keywords.yaml")
    seen_names: set[str] = set()
    projects: list[Project] = []

    filters_config = load_yaml_config("filters.yaml")
    min_stars = filters_config.get("github_min_stars", 200)

    for category, keywords in keywords_config.items():
        if not keywords:
            continue
        logger.info("Searching GitHub for category %s with keywords: %s", category, keywords)
        query = _build_search_query(keywords, min_stars=min_stars)
        items = _fetch_search_results(query, token=token, max_results=max_results_per_category)

        for item in items:
            full_name = item["full_name"]
            if full_name in seen_names:
                continue
            seen_names.add(full_name)

            project = _github_item_to_project(item)
            project.tags = [category]

            if enrich_readme:
                summary = _fetch_readme_summary(full_name, token=token)
                if summary:
                    project.readme_summary = summary
                    project.has_quickstart = "quickstart" in summary.lower() or "getting started" in summary.lower()

            projects.append(project)

            if len(projects) >= total_max:
                return projects

    return projects


def refresh_project_metadata(
    project: Project,
    *,
    token: str | None = None,
) -> Project:
    """Refresh a single project's metadata from the GitHub API.

    Updates stars, forks, open_issues, language, topics, license,
    last_pushed_at in-place and returns the same object.
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            f"{_GITHUB_API}/repos/{project.repo_full_name}",
            headers=headers,
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Failed to refresh %s: %s", project.repo_full_name, exc)
        return project

    if resp.status_code != 200:
        logger.warning("Could not refresh %s: HTTP %s", project.repo_full_name, resp.status_code)
        return project

    data = resp.json()
    project.stars = data.get("stargazers_count", project.stars)
    project.forks = data.get("forks_count", project.forks)
    project.open_issues = data.get("open_issues_count", project.open_issues)
    project.language = data.get("language", project.language)
    project.topics = data.get("topics", project.topics)
    project.license = data.get("license", {}).get("spdx_id") if data.get("license") else project.license
    project.last_pushed_at = data.get("pushed_at", project.last_pushed_at)
    project.last_checked_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    return project
