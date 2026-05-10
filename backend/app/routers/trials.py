"""Trials router: list, detail, status transitions, update."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.repositories import ProjectRepository, TrialRepository
from app.services.state_machine import (
    TRIAL_ALL_STATUSES,
    TRIAL_STATUS_META,
    get_allowed_trial_transitions,
    validate_trial_transition,
)

router = APIRouter()


class TrialOut(BaseModel):
    id: int
    project_id: int
    owner: str
    status: str
    claimed_at: str | None = None
    due_date: str | None = None
    environment: str | None = None
    demo_url: str | None = None
    trial_notes: str | None = None
    blockers: str | None = None
    result_summary: str | None = None
    next_action: str | None = None
    project_name: str | None = None


class TransitionRequest(BaseModel):
    target_status: str
    blockers: str | None = None
    result_summary: str | None = None
    drop_reason: str | None = None


class TrialUpdateRequest(BaseModel):
    owner: str | None = None
    due_date: str | None = None
    environment: str | None = None
    demo_url: str | None = None
    trial_notes: str | None = None
    result_summary: str | None = None
    next_action: str | None = None


def _to_out(t, project_name: str | None = None) -> TrialOut:
    return TrialOut(
        id=t.id,
        project_id=t.project_id,
        owner=t.owner,
        status=t.status,
        claimed_at=t.claimed_at.strftime("%Y-%m-%d %H:%M:%S") if t.claimed_at else None,
        due_date=str(t.due_date) if t.due_date else None,
        environment=t.environment,
        demo_url=t.demo_url,
        trial_notes=t.trial_notes,
        blockers=t.blockers,
        result_summary=t.result_summary,
        next_action=t.next_action,
        project_name=project_name,
    )


@router.get("/statuses")
async def list_statuses():
    """Return all trial statuses with metadata."""
    return {s: TRIAL_STATUS_META.get(s, {}) for s in TRIAL_ALL_STATUSES}


@router.get("/transitions")
async def get_transitions(status: str):
    """Return allowed transitions for a given status."""
    transitions = get_allowed_trial_transitions(status)
    return [
        {
            "target": t.target,
            "label": t.label,
            "description": t.description,
        }
        for t in transitions
    ]


@router.get("", response_model=list[TrialOut])
async def list_trials(
    status: str | None = None,
    owner: str | None = None,
    session: Session = Depends(get_session),
):
    repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    trials = repo.list_all()
    if status:
        trials = [t for t in trials if t.status == status]
    if owner:
        trials = [t for t in trials if owner.lower() in t.owner.lower()]

    result = []
    for t in trials:
        project = project_repo.get(t.project_id)
        result.append(_to_out(t, project.name if project else None))
    return result


@router.get("/{trial_id}", response_model=TrialOut)
async def get_trial(trial_id: int, session: Session = Depends(get_session)):
    repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    trial = repo.get(trial_id)
    if trial is None:
        raise HTTPException(404, "Trial not found")

    project = project_repo.get(trial.project_id)
    return _to_out(trial, project.name if project else None)


@router.post("/{trial_id}/transition", response_model=TrialOut)
async def transition_trial(
    trial_id: int,
    req: TransitionRequest,
    session: Session = Depends(get_session),
):
    repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    trial = repo.get(trial_id)
    if trial is None:
        raise HTTPException(404, "Trial not found")

    # Apply side effects before validation
    if req.target_status == "blocked" and req.blockers:
        trial.blockers = req.blockers.strip()
    if req.target_status == "demo_done" and req.result_summary:
        trial.result_summary = req.result_summary.strip()

    # Validate
    error = validate_trial_transition(trial, req.target_status)
    if error:
        raise HTTPException(400, error)

    # Apply
    trial.status = req.target_status

    if req.drop_reason and req.drop_reason.strip():
        trial.trial_notes = (
            (trial.trial_notes or "") + f"\n[Dropped: {req.drop_reason.strip()}]"
        ).strip()

    repo.update(trial)

    project = project_repo.get(trial.project_id)
    return _to_out(trial, project.name if project else None)


@router.put("/{trial_id}", response_model=TrialOut)
async def update_trial(
    trial_id: int,
    req: TrialUpdateRequest,
    session: Session = Depends(get_session),
):
    repo = TrialRepository(session)
    project_repo = ProjectRepository(session)

    trial = repo.get(trial_id)
    if trial is None:
        raise HTTPException(404, "Trial not found")

    if req.owner is not None:
        trial.owner = req.owner.strip()
    if req.due_date is not None:
        from datetime import date

        trial.due_date = date.fromisoformat(req.due_date) if req.due_date else None
    if req.environment is not None:
        trial.environment = req.environment.strip() or None
    if req.demo_url is not None:
        trial.demo_url = req.demo_url.strip() or None
    if req.trial_notes is not None:
        trial.trial_notes = req.trial_notes.strip() or None
    if req.result_summary is not None:
        trial.result_summary = req.result_summary.strip() or None
    if req.next_action is not None:
        trial.next_action = req.next_action.strip() or None

    repo.update(trial)

    project = project_repo.get(trial.project_id)
    return _to_out(trial, project.name if project else None)
