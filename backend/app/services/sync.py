"""Sync service: run project refresh in a background thread."""

from __future__ import annotations

import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so src.* imports work
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.config import load_yaml_config
from src.db import get_session, init_db
from src.models import Project
from src.repositories import ProjectRepository
from src.sources.github_search import search_candidate_projects
from src.sources.github_trending import fetch_trending_projects

logger = logging.getLogger(__name__)

# Module-level state
_sync_lock = threading.Lock()
_sync_running = False
_sync_result: dict | None = None


def get_sync_status() -> dict:
    """Return current sync status."""
    if _sync_running:
        return {"status": "running"}
    if _sync_result:
        return {"status": "idle", "last_result": _sync_result}
    return {"status": "idle", "last_result": None}


def _do_refresh() -> None:
    """Run the actual refresh (called in background thread)."""
    global _sync_running, _sync_result

    try:
        init_db()
        filters_config = load_yaml_config("filters.yaml")
        daily_limit = filters_config.get("daily_candidate_limit", 50)

        all_candidates: list[Project] = []

        # GitHub Search
        logger.info("Sync: searching GitHub...")
        candidates = search_candidate_projects(
            max_results_per_category=10,
            total_max=daily_limit,
            enrich_readme=False,
        )
        all_candidates.extend(candidates)
        logger.info("Sync: found %d from GitHub Search", len(candidates))

        # GitHub Trending
        logger.info("Sync: fetching GitHub Trending...")
        trending = fetch_trending_projects(since="daily", max_per_language=25)
        all_candidates.extend(trending)
        logger.info("Sync: found %d from GitHub Trending", len(trending))

        # Deduplicate
        seen: set[str] = set()
        unique: list[Project] = []
        for p in all_candidates:
            if p.repo_full_name not in seen:
                seen.add(p.repo_full_name)
                unique.append(p)

        # Save
        inserted = 0
        skipped = 0
        with get_session() as session:
            repo = ProjectRepository(session)
            for project in unique:
                existing = repo.get_by_repo_full_name(project.repo_full_name)
                if existing:
                    skipped += 1
                    continue
                repo.upsert(project)
                inserted += 1

        logger.info("Sync complete: %d new, %d already known", inserted, skipped)
        _sync_result = {
            "inserted": inserted,
            "skipped": skipped,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        logger.exception("Sync failed")
        _sync_result = {
            "error": True,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    finally:
        _sync_running = False


def start_sync() -> dict:
    """Start a sync in a background thread. Returns immediately."""
    global _sync_running

    with _sync_lock:
        if _sync_running:
            return {"status": "already_running"}
        _sync_running = True

    thread = threading.Thread(target=_do_refresh, daemon=True)
    thread.start()
    return {"status": "started"}
