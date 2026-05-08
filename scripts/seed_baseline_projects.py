"""Seed the database with baseline projects.

Usage::

    python scripts/seed_baseline_projects.py
"""

from src.db import get_session, init_db
from src.repositories import ProjectRepository
from src.sources.baseline_sources import get_baseline_projects


def main() -> None:
    init_db()

    projects = get_baseline_projects()
    inserted = 0
    skipped = 0

    with get_session() as session:
        repo = ProjectRepository(session)
        for project in projects:
            existing = repo.get_by_repo_full_name(project.repo_full_name)
            if existing:
                skipped += 1
                continue
            repo.upsert(project)
            inserted += 1

    print(f"Baseline seeding complete: {inserted} inserted, {skipped} already existed.")


if __name__ == "__main__":
    main()
