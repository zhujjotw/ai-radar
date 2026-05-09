"""Refresh metadata (stars, forks, etc.) for all existing projects from GitHub API.

Usage::

    python scripts/update_metadata.py
"""

import logging

from src.config import get_settings
from src.db import get_session, init_db
from src.repositories import ProjectRepository
from src.sources.github_search import refresh_project_metadata

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    init_db()
    token = get_settings().github_token

    with get_session() as session:
        repo = ProjectRepository(session)
        projects = repo.list_with_options()

    total = len(projects)
    updated = 0
    failed = 0

    logger.info("Refreshing metadata for %d projects...", total)

    for i, project in enumerate(projects, 1):
        logger.info("[%d/%d] %s", i, total, project.repo_full_name)
        refresh_project_metadata(project, token=token)
        try:
            with get_session() as session:
                repo = ProjectRepository(session)
                repo.update(project)
            updated += 1
        except Exception as exc:
            logger.error("Failed to save %s: %s", project.repo_full_name, exc)
            failed += 1

    logger.info("Done: %d updated, %d failed out of %d total", updated, failed, total)


if __name__ == "__main__":
    main()
