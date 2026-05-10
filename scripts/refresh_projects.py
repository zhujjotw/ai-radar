"""Refresh candidate projects from multiple sources.

Sources:
  - GitHub Search: keyword-based search from config/keywords.yaml
  - GitHub Trending: scrape github.com/trending for hot repos

Usage::

    python scripts/refresh_projects.py                    # all sources
    python scripts/refresh_projects.py --source search    # GitHub Search only
    python scripts/refresh_projects.py --source trending  # GitHub Trending only
    python scripts/refresh_projects.py --since weekly     # weekly trending
    python scripts/refresh_projects.py --languages python,typescript
"""

import argparse
import logging

from src.config import load_yaml_config
from src.db import get_session, init_db
from src.models import Project
from src.repositories import ProjectRepository
from src.sources.github_search import search_candidate_projects
from src.sources.github_trending import fetch_trending_projects

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _refresh_from_search(daily_limit: int) -> list[Project]:
    """Fetch candidates from GitHub Search."""
    logger.info("Searching GitHub for new candidate projects (limit=%d)…", daily_limit)
    candidates = search_candidate_projects(
        max_results_per_category=10,
        total_max=daily_limit,
        enrich_readme=False,
    )
    logger.info("Found %d candidate(s) from GitHub Search", len(candidates))
    return candidates


def _refresh_from_trending(
    since: str = "daily",
    languages: list[str] | None = None,
) -> list[Project]:
    """Fetch candidates from GitHub Trending."""
    logger.info(
        "Fetching GitHub Trending projects (since=%s, languages=%s)…",
        since,
        languages or "all",
    )
    candidates = fetch_trending_projects(
        since=since,
        languages=languages,
        max_per_language=25,
    )
    logger.info("Found %d candidate(s) from GitHub Trending", len(candidates))
    return candidates


def _save_candidates(candidates: list[Project]) -> tuple[int, int]:
    """Save candidates to database, return (inserted, skipped) counts."""
    inserted = 0
    skipped = 0

    with get_session() as session:
        repo = ProjectRepository(session)
        for project in candidates:
            existing = repo.get_by_repo_full_name(project.repo_full_name)
            if existing:
                skipped += 1
                # Update trending source info if coming from trending
                if project.source == "github_trending" and existing.source != "github_trending":
                    existing.source = "github_trending"
                    existing.discovered_reason = project.discovered_reason
                    repo.update(existing)
                continue
            repo.upsert(project)
            inserted += 1

    return inserted, skipped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh candidate projects")
    parser.add_argument(
        "--source",
        choices=["all", "search", "trending"],
        default="all",
        help="Which source to refresh (default: all)",
    )
    parser.add_argument(
        "--since",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Trending time range (default: daily)",
    )
    parser.add_argument(
        "--languages",
        type=str,
        default=None,
        help="Comma-separated languages for trending filter (e.g. python,typescript)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db()

    filters_config = load_yaml_config("filters.yaml")
    daily_limit = filters_config.get("daily_candidate_limit", 50)

    all_candidates: list[Project] = []

    # GitHub Search
    if args.source in ("all", "search"):
        all_candidates.extend(_refresh_from_search(daily_limit))

    # GitHub Trending
    if args.source in ("all", "trending"):
        languages = args.languages.split(",") if args.languages else None
        all_candidates.extend(_refresh_from_trending(since=args.since, languages=languages))

    # Deduplicate by repo_full_name before saving
    seen: set[str] = set()
    unique_candidates: list[Project] = []
    for p in all_candidates:
        if p.repo_full_name not in seen:
            seen.add(p.repo_full_name)
            unique_candidates.append(p)

    inserted, skipped = _save_candidates(unique_candidates)
    logger.info("Refresh complete: %d new, %d already known", inserted, skipped)


if __name__ == "__main__":
    main()
