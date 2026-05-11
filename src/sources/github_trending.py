"""GitHub Trending page scraper for discovering hot AI projects.

Scrapes https://github.com/trending to find repositories that are
gaining traction right now.  Supports daily, weekly, and monthly
time ranges, as well as optional language filtering.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import requests

from src.models import Project

logger = logging.getLogger(__name__)

_TRENDING_URL = "https://github.com/trending"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _parse_trending_html(html: str) -> list[dict]:
    """Parse GitHub Trending HTML into a list of repo dicts.

    Returns list of dicts with keys:
        full_name, description, language, stars, forks, trending_stars
    """
    repos: list[dict] = []

    # Split by article tags
    articles = re.split(r'<article\s+class="Box-row"', html)
    for article_html in articles[1:]:  # skip first chunk before first article
        repo: dict = {}

        # Extract repo full_name from h2 > a href
        name_match = re.search(
            r'<h2[^>]*>.*?href="/([^/]+/[^/"]+)"',
            article_html,
            re.DOTALL,
        )
        if not name_match:
            continue
        repo["full_name"] = name_match.group(1).strip()

        # Extract description from <p class="col-9 ...">
        desc_match = re.search(
            r'<p\s+class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>',
            article_html,
            re.DOTALL,
        )
        if desc_match:
            desc = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()
            repo["description"] = desc if desc else None
        else:
            repo["description"] = None

        # Extract language (clean any HTML tags)
        lang_match = re.search(
            r'itemprop="programmingLanguage"[^>]*>\s*(?:<[^>]+>)?\s*(\w+)',
            article_html,
        )
        if lang_match:
            # Use the last capturing group which should be the language name
            language = lang_match.group(2) if lang_match.lastindex >= 2 else lang_match.group(1)
            # Clean any remaining HTML tags
            language = re.sub(r'<[^>]+>', '', language).strip()
        else:
            language = None
        repo["language"] = language

        # Extract total stars from stargazers link
        stars_match = re.search(
            r'href="/[^"]+/stargazers"[^>]*>.*?([\d,]+)\s*</a>',
            article_html,
            re.DOTALL,
        )
        if stars_match:
            repo["stars"] = int(stars_match.group(1).replace(",", ""))
        else:
            repo["stars"] = 0

        # Extract total forks from forks link
        forks_match = re.search(
            r'href="/[^"]+/forks"[^>]*>.*?([\d,]+)\s*</a>',
            article_html,
            re.DOTALL,
        )
        if forks_match:
            repo["forks"] = int(forks_match.group(1).replace(",", ""))
        else:
            repo["forks"] = 0

        # Extract trending stars (e.g. "3,660 stars today")
        trending_match = re.search(
            r'([\d,]+)\s+stars?\s+(today|this week|this month)',
            article_html,
        )
        if trending_match:
            repo["trending_stars"] = int(trending_match.group(1).replace(",", ""))
            repo["trending_period"] = trending_match.group(2)
        else:
            repo["trending_stars"] = 0
            repo["trending_period"] = None

        repos.append(repo)

    return repos


def _fetch_trending_page(
    *,
    since: str = "daily",
    language: str | None = None,
) -> str | None:
    """Fetch the GitHub Trending page HTML.

    Parameters
    ----------
    since:
        Time range: "daily", "weekly", or "monthly".
    language:
        Optional language filter (e.g. "python", "rust").
    """
    url = _TRENDING_URL
    if language:
        url = f"{_TRENDING_URL}/{language.lower()}"
    url = f"{url}?since={since}"

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        logger.error("Failed to fetch GitHub Trending: %s", exc)
        return None

    if resp.status_code != 200:
        logger.warning("GitHub Trending returned HTTP %s", resp.status_code)
        return None

    return resp.text


def _item_to_project(item: dict) -> Project:
    """Convert a parsed trending item to a Project model."""
    full_name = item["full_name"]
    github_url = f"https://github.com/{full_name}"
    # Extract owner from full_name (format: "owner/repo")
    owner = full_name.split("/")[0] if "/" in full_name else None

    # Clean language field of HTML tags
    language = item.get("language")
    if language:
        language = re.sub(r'<[^>]+>', '', str(language)).strip()

    return Project(
        github_url=github_url,
        repo_full_name=full_name,
        name=full_name.split("/")[-1],
        owner=owner,
        description=item.get("description"),
        pool="candidate",
        source="github_trending",
        discovered_reason=f"Trending: {item.get('trending_stars', 0)} stars "
        f"{item.get('trending_period', 'today')}",
        stars=item.get("stars", 0),
        forks=item.get("forks", 0),
        language=language,
        topics=[],
        tags=[],
        last_pushed_at=None,
        last_checked_at=datetime.now(tz=timezone.utc),
    )


def fetch_trending_projects(
    *,
    since: str = "daily",
    languages: list[str] | None = None,
    max_per_language: int = 25,
) -> list[Project]:
    """Fetch trending projects from GitHub Trending page.

    Parameters
    ----------
    since:
        Time range: "daily", "weekly", or "monthly".
    languages:
        List of languages to filter by.  None means all languages.
    max_per_language:
        Max repos to return per language/page.

    Returns
    -------
    list[Project]
        Deduplicated list of trending projects.
    """
    if languages is None:
        languages = [None]  # type: ignore[list-item]

    seen: set[str] = set()
    projects: list[Project] = []

    for lang in languages:
        logger.info("Fetching GitHub Trending (since=%s, language=%s)", since, lang or "all")
        html = _fetch_trending_page(since=since, language=lang)
        if not html:
            continue

        items = _parse_trending_html(html)
        logger.info("Parsed %d trending repos for language=%s", len(items), lang or "all")

        for item in items[:max_per_language]:
            full_name = item["full_name"]
            if full_name in seen:
                continue
            seen.add(full_name)
            project = _item_to_project(item)
            # Add trending tag
            project.tags = ["Trending"]
            projects.append(project)

        # Be polite between requests
        if len(languages) > 1:
            time.sleep(1)

    logger.info("Total trending projects found: %d", len(projects))
    return projects
