"""Refresh candidate projects from GitHub Search.

Runs a GitHub search for each keyword category in ``config/keywords.yaml``,
deduplicates against the database, and inserts new candidates.

Usage::

    python scripts/refresh_projects.py
"""

import logging

from src.config import load_yaml_config
from src.db import get_session, init_db
from src.repositories import ProjectRepository
from src.sources.github_search import search_candidate_projects

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    init_db()

    filters_config = load_yaml_config("filters.yaml")
    daily_limit = filters_config.get("daily_candidate_limit", 10)

    logger.info("Searching GitHub for new candidate projects (limit=%d)…", daily_limit)
    candidates = search_candidate_projects(total_max=daily_limit, enrich_readme=False)
    logger.info("Found %d candidate(s) from GitHub Search", len(candidates))

    inserted = 0
    updated = 0

    with get_session() as session:
        repo = ProjectRepository(session)
        for project in candidates:
            existing = repo.get_by_repo_full_name(project.repo_full_name)
            if existing:
                updated += 1
                continue
            repo.upsert(project)
            inserted += 1

    logger.info("Refresh complete: %d new, %d already known", inserted, updated)


if __name__ == "__main__":
    main()
