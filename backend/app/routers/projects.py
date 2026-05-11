"""Projects router: list, detail, tags, claim."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.auth import AuthUser, get_current_user
from app.config import get_settings
from app.db import get_session
from app.models import Evaluation, Trial
from app.repositories import EvaluationRepository, ProjectRepository, TrialRepository

router = APIRouter()

_GITHUB_API_URL = "https://api.github.com/repos"
_GITHUB_RAW_BASE = "https://raw.githubusercontent.com"


class ProjectListItem(BaseModel):
    id: int
    name: str
    github_url: str
    repo_full_name: str
    description: str | None = None
    pool: str
    source: str
    stars: int
    forks: int
    open_issues: int
    language: str | None = None
    tags: list[str] = []
    topics: list[str] = []
    license: str | None = None
    filter_status: str
    last_pushed_at: str | None = None
    first_seen_at: str | None = None
    llm_description: str | None = None
    llm_scenarios: str | None = None
    # Aggregated data
    latest_evaluation: dict | None = None
    active_trial: dict | None = None
    owner: str = ""


class ProjectDetail(BaseModel):
    id: int
    name: str
    github_url: str
    repo_full_name: str
    description: str | None = None
    pool: str
    source: str
    source_url: str | None = None
    discovered_reason: str | None = None
    stars: int
    forks: int
    open_issues: int
    language: str | None = None
    topics: list[str] = []
    tags: list[str] = []
    license: str | None = None
    has_quickstart: bool = False
    readme_summary: str | None = None
    last_pushed_at: str | None = None
    first_seen_at: str | None = None
    filter_status: str
    filter_reason: str | None = None
    llm_description: str | None = None
    llm_scenarios: str | None = None
    latest_evaluation: dict | None = None
    active_trial: dict | None = None
    owner: str = ""


def _eval_to_dict(e: Evaluation | None) -> dict | None:
    if e is None:
        return None
    return {
        "id": e.id,
        "relevance_score": e.relevance_score,
        "trialability_score": e.trialability_score,
        "value_score": e.value_score,
        "recommendation_score": e.recommendation_score,
        "decision": e.decision,
        "decision_reason": e.decision_reason,
        "evidence": e.evidence,
    }


def _trial_to_dict(t: Trial | None) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.id,
        "owner": t.owner,
        "status": t.status,
        "due_date": str(t.due_date) if t.due_date else None,
        "environment": t.environment,
        "demo_url": t.demo_url,
        "trial_notes": t.trial_notes,
        "result_summary": t.result_summary,
        "blockers": t.blockers,
        "next_action": t.next_action,
    }


def _fmt_dt(dt) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


def _get_active_trial(trials: list[Trial]) -> Trial | None:
    active = [t for t in trials if t.status not in ("dropped",)]
    return active[-1] if active else None


def _parse_github_url(url: str) -> tuple[str, str] | None:
    """Parse GitHub URL to extract owner and repo name.

    Returns (owner, repo) tuple or None if invalid.
    Supports: github.com/owner/repo, github.com/owner/repo/
    """
    # Match github.com/owner/repo format
    match = re.match(r'https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/?', url)
    if match:
        return match.group(1), match.group(2)
    return None


def _fetch_github_repo_info(owner: str, repo: str) -> dict[str, Any] | None:
    """Fetch repository information from GitHub API.

    Returns dict with repo metadata or None if failed.
    """
    settings = get_settings()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"

    try:
        # Fetch basic repo info
        url = f"{_GITHUB_API_URL}/{owner}/{repo}"
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return None

        data = resp.json()

        # Extract topics (need separate request or they're in the same response)
        topics = data.get("topics", [])

        return {
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "language": data.get("language"),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
            "topics": topics,
            "homepage": data.get("homepage"),
            "pushed_at": data.get("pushed_at"),
            "created_at": data.get("created_at"),
        }
    except Exception:
        return None


class AddProjectFromUrlRequest(BaseModel):
    github_url: str


@router.post("/from-github")
async def add_project_from_github_url(
    req: AddProjectFromUrlRequest,
    session: Session = Depends(get_session),
):
    """Add a project by fetching its information from GitHub URL.

    Validates the URL, fetches repository info from GitHub API,
    and creates a new project in the database.
    """
    # Validate GitHub URL
    parsed = _parse_github_url(req.github_url)
    if not parsed:
        raise HTTPException(400, "Invalid GitHub URL. Must be a github.com repository URL.")

    owner, repo = parsed
    full_name = f"{owner}/{repo}"

    # Check if already exists
    repo_repo = ProjectRepository(session)
    existing = repo_repo.get_by_repo_full_name(full_name)
    if existing:
        raise HTTPException(400, f"Project {full_name} already exists in the database.")

    # Fetch repository info from GitHub API
    repo_info = _fetch_github_repo_info(owner, repo)
    if not repo_info:
        raise HTTPException(404, f"Failed to fetch repository information for {full_name}. Check the URL and try again.")

    # Create project model
    from app.models import Project

    project = Project(
        github_url=req.github_url,
        repo_full_name=full_name,
        name=repo_info["name"],
        owner=owner,
        description=repo_info.get("description"),
        pool="candidate",
        source="manual",
        discovered_reason=f"Manually added from GitHub URL",
        stars=repo_info["stars"],
        forks=repo_info["forks"],
        open_issues=repo_info["open_issues"],
        language=repo_info.get("language"),
        license=repo_info.get("license"),
        topics=repo_info.get("topics", []),
        tags=[],
        last_pushed_at=datetime.fromisoformat(repo_info["pushed_at"].replace("Z", "+00:00")) if repo_info.get("pushed_at") else datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
        last_checked_at=datetime.now(timezone.utc),
    )

    # Save to database
    created = repo_repo.upsert(project)

    return {
        "message": f"Successfully added {full_name}",
        "project": {
            "id": created.id,
            "name": created.name,
            "full_name": created.repo_full_name,
            "stars": created.stars,
            "language": created.language,
        }
    }



@router.get("", response_model=list[ProjectListItem])
async def list_projects(
    tag: str | None = None,
    order_by: str = "recommendation_sort",
    order_desc: bool = True,
    pool: str | None = None,
    source: str | None = None,
    filter_status: str | None = None,
    decision: str | None = None,
    session: Session = Depends(get_session),
):
    repo = ProjectRepository(session)
    eval_repo = EvaluationRepository(session)
    trial_repo = TrialRepository(session)

    kw: dict = {}
    if tag:
        kw["tag"] = tag
    if pool:
        kw["pool"] = pool
    if source:
        kw["source"] = source
    if filter_status:
        kw["filter_status"] = filter_status
    if decision:
        kw["decision"] = decision

    # Handle special sort modes
    if order_by in ("recommendation_sort", "unevaluated_sort"):
        projects = repo.list_with_options(**kw)
    else:
        projects = repo.list_with_options(**kw, order_by=order_by, order_desc=order_desc)

    # In-memory sorting for special modes
    if order_by == "recommendation_sort":
        _eval_cache: dict[int, Evaluation | None] = {}
        for p in projects:
            if p.id and p.id not in _eval_cache:
                _eval_cache[p.id] = eval_repo.get_latest_by_project(p.id)
        projects.sort(
            key=lambda p: (
                _eval_cache.get(p.id) is not None,
                (getattr(_eval_cache.get(p.id), "recommendation_score", None) or 0),
            ),
            reverse=True,
        )
    elif order_by == "unevaluated_sort":
        _eval_cache_unev: dict[int, Evaluation | None] = {}
        for p in projects:
            if p.id and p.id not in _eval_cache_unev:
                _eval_cache_unev[p.id] = eval_repo.get_latest_by_project(p.id)
        projects.sort(
            key=lambda p: _eval_cache_unev.get(p.id) is None,
            reverse=True,
        )

    # Pre-load trial data
    _trial_cache: dict[int, list[Trial]] = {}
    for p in projects:
        if p.id and p.id not in _trial_cache:
            _trial_cache[p.id] = trial_repo.list_by_project(p.id)

    items = []
    for p in projects:
        evaluation = eval_repo.get_latest_by_project(p.id) if p.id else None
        trials = _trial_cache.get(p.id, [])
        active = _get_active_trial(trials)
        # Use project owner instead of trial owner
        owner = p.owner or ""

        items.append(
            ProjectListItem(
                id=p.id,
                name=p.name,
                github_url=p.github_url,
                repo_full_name=p.repo_full_name,
                description=p.description,
                pool=p.pool,
                source=p.source,
                stars=p.stars,
                forks=p.forks,
                open_issues=p.open_issues,
                language=p.language,
                tags=p.tags or [],
                topics=p.topics or [],
                license=p.license,
                filter_status=p.filter_status,
                last_pushed_at=_fmt_dt(p.last_pushed_at),
                first_seen_at=_fmt_dt(p.first_seen_at),
                llm_description=p.llm_description,
                llm_scenarios=p.llm_scenarios,
                latest_evaluation=_eval_to_dict(evaluation),
                active_trial=_trial_to_dict(active),
                owner=owner,
            )
        )
    return items


@router.get("/tags", response_model=list[str])
async def list_tags(session: Session = Depends(get_session)):
    repo = ProjectRepository(session)
    return repo.get_all_tags()


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(project_id: int, session: Session = Depends(get_session)):
    repo = ProjectRepository(session)
    eval_repo = EvaluationRepository(session)
    trial_repo = TrialRepository(session)

    project = repo.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    evaluation = eval_repo.get_latest_by_project(project_id)
    trials = trial_repo.list_by_project(project_id)
    active = _get_active_trial(trials)
    # Use project owner instead of trial owner
    owner = project.owner or ""

    return ProjectDetail(
        id=project.id,
        name=project.name,
        github_url=project.github_url,
        repo_full_name=project.repo_full_name,
        description=project.description,
        pool=project.pool,
        source=project.source,
        source_url=project.source_url,
        discovered_reason=project.discovered_reason,
        stars=project.stars,
        forks=project.forks,
        open_issues=project.open_issues,
        language=project.language,
        topics=project.topics or [],
        tags=project.tags or [],
        license=project.license,
        has_quickstart=project.has_quickstart,
        readme_summary=project.readme_summary,
        last_pushed_at=_fmt_dt(project.last_pushed_at),
        first_seen_at=_fmt_dt(project.first_seen_at),
        filter_status=project.filter_status,
        filter_reason=project.filter_reason,
        llm_description=project.llm_description,
        llm_scenarios=project.llm_scenarios,
        latest_evaluation=_eval_to_dict(evaluation),
        active_trial=_trial_to_dict(active),
        owner=owner,
    )


@router.post("/{project_id}/claim")
async def claim_project(
    project_id: int,
    current_user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    repo = ProjectRepository(session)
    eval_repo = EvaluationRepository(session)
    trial_repo = TrialRepository(session)

    project = repo.get(project_id)
    if project is None:
        raise HTTPException(404, "Project not found")

    # Check if already claimed
    trials = trial_repo.list_by_project(project_id)
    active = _get_active_trial(trials)
    if active:
        raise HTTPException(400, f"Already claimed by {active.owner}")

    # Create or update evaluation to "try"
    evaluation = eval_repo.get_latest_by_project(project_id)
    if evaluation:
        if evaluation.decision != "try":
            evaluation.decision = "try"
            eval_repo.update(evaluation)
    else:
        from app.models import Evaluation

        evaluation = Evaluation(project_id=project_id, decision="try")
        eval_repo.create(evaluation)

    # Create trial
    from app.models import Trial

    trial = Trial(
        project_id=project_id,
        owner=current_user.username,
        status="claimed",
    )
    trial_repo.create(trial)

    return {"message": f"Claimed {project.name}", "project": project.name, "owner": current_user.username}
