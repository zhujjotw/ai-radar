"""Evaluations router: CRUD for project evaluations."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.repositories import EvaluationRepository

router = APIRouter()


class EvaluationOut(BaseModel):
    id: int
    project_id: int
    relevance_score: int | None = None
    trialability_score: int | None = None
    value_score: int | None = None
    recommendation_score: int | None = None
    decision: str
    decision_reason: str | None = None
    evidence: str | None = None
    evaluated_by: str | None = None
    evaluated_at: str | None = None


def _to_out(e) -> EvaluationOut:
    return EvaluationOut(
        id=e.id,
        project_id=e.project_id,
        relevance_score=e.relevance_score,
        trialability_score=e.trialability_score,
        value_score=e.value_score,
        recommendation_score=e.recommendation_score,
        decision=e.decision,
        decision_reason=e.decision_reason,
        evidence=e.evidence,
        evaluated_by=e.evaluated_by,
        evaluated_at=e.evaluated_at.strftime("%Y-%m-%d %H:%M:%S") if e.evaluated_at else None,
    )


@router.get("/project/{project_id}/latest", response_model=EvaluationOut | None)
async def get_latest_evaluation(project_id: int, session: Session = Depends(get_session)):
    repo = EvaluationRepository(session)
    ev = repo.get_latest_by_project(project_id)
    return _to_out(ev) if ev else None


@router.get("/project/{project_id}", response_model=list[EvaluationOut])
async def list_evaluations(project_id: int, session: Session = Depends(get_session)):
    repo = EvaluationRepository(session)
    return [_to_out(e) for e in repo.list_by_project(project_id)]
