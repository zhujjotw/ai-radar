"""Shares router: create, list, markdown export."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.models import Share
from app.repositories import ProjectRepository, ShareRepository, TrialRepository
from app.services.graph_builder import build_share_graph
from app.services.markdown_export import export_share_markdown

router = APIRouter()


class ShareOut(BaseModel):
    id: int
    trial_id: int
    title: str
    summary: str | None = None
    key_findings: str | None = None
    reusable_patterns: str | None = None
    applicable_scenarios: str | None = None
    knowledge_doc_url: str | None = None
    shared_at: str | None = None
    shared_by: str | None = None
    project_name: str | None = None


class CreateShareRequest(BaseModel):
    trial_id: int
    title: str
    summary: str | None = None
    key_findings: str | None = None
    reusable_patterns: str | None = None
    applicable_scenarios: str | None = None
    knowledge_doc_url: str | None = None
    shared_by: str | None = None


def _to_out(s, project_name: str | None = None) -> ShareOut:
    return ShareOut(
        id=s.id,
        trial_id=s.trial_id,
        title=s.title,
        summary=s.summary,
        key_findings=s.key_findings,
        reusable_patterns=s.reusable_patterns,
        applicable_scenarios=s.applicable_scenarios,
        knowledge_doc_url=s.knowledge_doc_url,
        shared_at=s.shared_at.strftime("%Y-%m-%d %H:%M:%S") if s.shared_at else None,
        shared_by=s.shared_by,
        project_name=project_name,
    )


@router.get("/ready-trials")
async def list_ready_trials(session: Session = Depends(get_session)):
    """List demo_done trials that don't have a share yet."""
    trial_repo = TrialRepository(session)
    share_repo = ShareRepository(session)
    project_repo = ProjectRepository(session)

    demo_done = trial_repo.list_by_status("demo_done")
    result = []
    for t in demo_done:
        existing = share_repo.get_by_trial_id(t.id)
        if existing is not None:
            continue
        project = project_repo.get(t.project_id)
        result.append({
            "trial_id": t.id,
            "project_name": project.name if project else "Unknown",
            "owner": t.owner,
            "result_summary": t.result_summary,
        })
    return result


@router.get("", response_model=list[ShareOut])
async def list_shares(
    shared_by: str | None = None,
    session: Session = Depends(get_session),
):
    share_repo = ShareRepository(session)
    trial_repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    shares = share_repo.list_all()
    if shared_by and shared_by.strip():
        shares = [s for s in shares if s.shared_by and shared_by.strip().lower() in s.shared_by.lower()]

    result = []
    for s in shares:
        trial = trial_repo.get(s.trial_id)
        project = project_repo.get(trial.project_id) if trial else None
        result.append(_to_out(s, project.name if project else None))
    return result


@router.post("", response_model=ShareOut)
async def create_share(req: CreateShareRequest, session: Session = Depends(get_session)):
    share_repo = ShareRepository(session)
    trial_repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    # Check trial exists
    trial = trial_repo.get(req.trial_id)
    if trial is None:
        raise HTTPException(404, "Trial not found")

    # Check not already shared
    existing = share_repo.get_by_trial_id(req.trial_id)
    if existing is not None:
        raise HTTPException(400, "Share already exists for this trial")

    # Create share
    share = Share(
        trial_id=req.trial_id,
        title=req.title.strip(),
        summary=req.summary.strip() if req.summary else None,
        key_findings=req.key_findings.strip() if req.key_findings else None,
        reusable_patterns=req.reusable_patterns.strip() if req.reusable_patterns else None,
        applicable_scenarios=req.applicable_scenarios.strip() if req.applicable_scenarios else None,
        knowledge_doc_url=req.knowledge_doc_url.strip() if req.knowledge_doc_url else None,
        shared_by=req.shared_by.strip() if req.shared_by else None,
    )
    share_repo.create(share)

    # Update trial status
    trial.status = "shared"
    trial_repo.update(trial)

    # Build graph
    build_share_graph(session, share)

    project = project_repo.get(trial.project_id)
    return _to_out(share, project.name if project else None)


@router.get("/{share_id}/markdown")
async def get_markdown(share_id: int, session: Session = Depends(get_session)):
    md = export_share_markdown(session, share_id)
    if not md:
        raise HTTPException(404, "Share not found")
    return {"markdown": md}


@router.get("/{share_id}")
async def get_share(share_id: int, session: Session = Depends(get_session)):
    share_repo = ShareRepository(session)
    trial_repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    share = share_repo.get(share_id)
    if share is None:
        raise HTTPException(404, "Share not found")

    trial = trial_repo.get(share.trial_id)
    project = project_repo.get(trial.project_id) if trial else None
    return _to_out(share, project.name if project else None)
