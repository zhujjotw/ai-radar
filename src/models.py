from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("repo_full_name", name="uq_projects_repo_full_name"),)

    id: int | None = Field(default=None, primary_key=True)
    github_url: str
    repo_full_name: str = Field(index=True)
    name: str
    description: str | None = None
    pool: str = Field(default="candidate", index=True)
    source: str = Field(default="manual", index=True)
    source_url: str | None = None
    discovered_reason: str | None = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    language: str | None = None
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    license: str | None = None
    has_quickstart: bool = False
    readme_summary: str | None = None
    last_pushed_at: datetime | None = None
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_checked_at: datetime | None = None
    is_archived: bool = False
    filter_status: str = Field(default="needs_review", index=True)
    filter_reason: str | None = None
    llm_description: str | None = None
    llm_scenarios: str | None = None


class Evaluation(SQLModel, table=True):
    __tablename__ = "evaluations"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    relevance_score: int | None = None
    trialability_score: int | None = None
    value_score: int | None = None
    recommendation_score: int | None = None
    decision: str = Field(default="watch", index=True)
    decision_reason: str | None = None
    evidence: str | None = None
    evaluated_by: str | None = None
    evaluated_at: datetime = Field(default_factory=utc_now)


class Trial(SQLModel, table=True):
    __tablename__ = "trials"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    owner: str = Field(index=True)
    status: str = Field(default="claimed", index=True)
    claimed_at: datetime = Field(default_factory=utc_now)
    due_date: date | None = None
    environment: str | None = None
    demo_url: str | None = None
    trial_notes: str | None = None
    blockers: str | None = None
    result_summary: str | None = None
    next_action: str | None = None


class Share(SQLModel, table=True):
    __tablename__ = "shares"

    id: int | None = Field(default=None, primary_key=True)
    trial_id: int = Field(foreign_key="trials.id", index=True)
    title: str
    summary: str | None = None
    key_findings: str | None = None
    reusable_patterns: str | None = None
    applicable_scenarios: str | None = None
    knowledge_doc_url: str | None = None
    shared_at: datetime = Field(default_factory=utc_now)
    shared_by: str | None = None


class GraphNode(SQLModel, table=True):
    __tablename__ = "graph_nodes"

    id: int | None = Field(default=None, primary_key=True)
    node_type: str = Field(index=True)
    name: str = Field(index=True)
    ref_table: str | None = None
    ref_id: int | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class GraphEdge(SQLModel, table=True):
    __tablename__ = "graph_edges"

    id: int | None = Field(default=None, primary_key=True)
    source_node_id: int = Field(foreign_key="graph_nodes.id", index=True)
    relation_type: str = Field(index=True)
    target_node_id: int = Field(foreign_key="graph_nodes.id", index=True)
    confidence: float = 1.0
    evidence: str | None = None
    source: str = Field(default="manual", index=True)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
