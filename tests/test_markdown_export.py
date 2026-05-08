"""Tests for T5 markdown_export module."""

from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from src.models import Evaluation, Project, Share, Trial
from src.services.graph_builder import build_project_graph, build_share_graph
from src.services.markdown_export import (
    export_evaluation_markdown,
    export_share_markdown,
    export_trial_markdown,
)


def _make_session() -> Session:
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _make_project(
    session: Session,
    *,
    name: str = "test-project",
    repo_full_name: str | None = None,
    tags: list[str] | None = None,
    topics: list[str] | None = None,
    description: str | None = None,
    stars: int = 100,
    language: str | None = "Python",
    license_spdx: str | None = "MIT",
    readme_summary: str | None = None,
) -> Project:
    """Helper to create and persist a Project."""
    project = Project(
        github_url=f"https://github.com/test/{name}",
        repo_full_name=repo_full_name or f"test/{name}",
        name=name,
        description=description,
        tags=tags or [],
        topics=topics or [],
        stars=stars,
        forks=10,
        language=language,
        license=license_spdx,
        readme_summary=readme_summary,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def _make_evaluation(
    session: Session,
    project_id: int,
    *,
    decision: str = "watch",
    relevance_score: int | None = None,
    trialability_score: int | None = None,
    value_score: int | None = None,
    recommendation_score: int | None = None,
    decision_reason: str | None = None,
    evidence: str | None = None,
    evaluated_by: str | None = None,
) -> Evaluation:
    """Helper to create and persist an Evaluation."""
    ev = Evaluation(
        project_id=project_id,
        decision=decision,
        relevance_score=relevance_score,
        trialability_score=trialability_score,
        value_score=value_score,
        recommendation_score=recommendation_score,
        decision_reason=decision_reason,
        evidence=evidence,
        evaluated_by=evaluated_by,
    )
    session.add(ev)
    session.commit()
    session.refresh(ev)
    return ev


def _make_trial(
    session: Session,
    project_id: int,
    *,
    owner: str = "alice",
    status: str = "claimed",
    trial_notes: str | None = None,
    result_summary: str | None = None,
    blockers: str | None = None,
    environment: str | None = None,
    demo_url: str | None = None,
    next_action: str | None = None,
    due_date: date | None = None,
) -> Trial:
    """Helper to create and persist a Trial."""
    trial = Trial(
        project_id=project_id,
        owner=owner,
        status=status,
        trial_notes=trial_notes,
        result_summary=result_summary,
        blockers=blockers,
        environment=environment,
        demo_url=demo_url,
        next_action=next_action,
        due_date=due_date,
    )
    session.add(trial)
    session.commit()
    session.refresh(trial)
    return trial


def _make_share(
    session: Session,
    trial_id: int,
    *,
    title: str = "Test Share",
    summary: str | None = None,
    key_findings: str | None = None,
    reusable_patterns: str | None = None,
    applicable_scenarios: str | None = None,
    knowledge_doc_url: str | None = None,
    shared_by: str | None = None,
) -> Share:
    """Helper to create and persist a Share."""
    share = Share(
        trial_id=trial_id,
        title=title,
        summary=summary,
        key_findings=key_findings,
        reusable_patterns=reusable_patterns,
        applicable_scenarios=applicable_scenarios,
        knowledge_doc_url=knowledge_doc_url,
        shared_by=shared_by,
    )
    session.add(share)
    session.commit()
    session.refresh(share)
    return share


# ── export_evaluation_markdown ─────────────────────────────────────


def test_export_evaluation_returns_empty_for_missing_project():
    session = _make_session()
    md = export_evaluation_markdown(session, project_id=999)
    assert md == ""


def test_export_evaluation_basic_project():
    session = _make_session()
    project = _make_project(session, name="langchain", description="LLM framework")

    md = export_evaluation_markdown(session, project.id)

    assert "# langchain" in md
    assert "https://github.com/test/langchain" in md
    assert "LLM framework" in md
    assert "## 项目信息" in md
    assert "| Stars | 100 |" in md
    assert "| Forks | 10 |" in md
    assert "| 语言 | Python |" in md
    assert "| 许可证 | MIT |" in md


def test_export_evaluation_with_tags_and_topics():
    session = _make_session()
    project = _make_project(
        session,
        name="agent-poc",
        tags=["Agent", "RAG"],
        topics=["llm", "agents"],
    )

    md = export_evaluation_markdown(session, project.id)

    assert "Agent, RAG" in md
    assert "llm, agents" in md


def test_export_evaluation_with_readme_summary():
    session = _make_session()
    project = _make_project(
        session,
        name="cool-tool",
        readme_summary="This is a cool tool for AI.",
    )

    md = export_evaluation_markdown(session, project.id)

    assert "## README 摘要" in md
    assert "This is a cool tool for AI." in md


def test_export_evaluation_no_readme_summary_omits_section():
    session = _make_session()
    project = _make_project(session, name="no-readme", readme_summary=None)

    md = export_evaluation_markdown(session, project.id)

    assert "README 摘要" not in md


def test_export_evaluation_with_evaluation():
    session = _make_session()
    project = _make_project(session, name="eval-project")
    _make_evaluation(
        session,
        project.id,
        decision="try",
        relevance_score=8,
        trialability_score=7,
        value_score=9,
        recommendation_score=8,
        decision_reason="High value for team",
        evidence="Stars growing fast",
        evaluated_by="bob",
    )

    md = export_evaluation_markdown(session, project.id)

    assert "## 评估记录" in md
    assert "### 评估 #1" in md
    assert "**推荐分**: 8" in md
    assert "**相关分**: 8" in md
    assert "**可试分**: 7" in md
    assert "**价值分**: 9" in md
    assert "**决策**: try" in md
    assert "High value for team" in md
    assert "Stars growing fast" in md
    assert "**评估人**: bob" in md


def test_export_evaluation_multiple_evaluations():
    session = _make_session()
    project = _make_project(session, name="multi-eval")
    _make_evaluation(session, project.id, decision="watch", evaluated_by="alice")
    _make_evaluation(session, project.id, decision="try", evaluated_by="bob")

    md = export_evaluation_markdown(session, project.id)

    assert "### 评估 #1" in md
    assert "### 评估 #2" in md


def test_export_evaluation_none_scores_show_dash():
    session = _make_session()
    project = _make_project(session, name="no-scores")
    _make_evaluation(session, project.id, relevance_score=None)

    md = export_evaluation_markdown(session, project.id)

    assert "**相关分**: -" in md


def test_export_evaluation_with_filter_status():
    session = _make_session()
    project = _make_project(session, name="filtered-proj")
    project.filter_status = "filtered_out"
    project.filter_reason = "Too few stars"
    session.add(project)
    session.commit()

    md = export_evaluation_markdown(session, project.id)

    assert "filtered_out" in md
    assert "Too few stars" in md


def test_export_evaluation_with_graph_relations():
    session = _make_session()
    project = _make_project(
        session,
        name="graph-proj",
        tags=["Agent"],
        topics=["chatbot"],
    )
    build_project_graph(session, project)

    md = export_evaluation_markdown(session, project.id)

    assert "## 图谱关系" in md
    assert "belongs_to" in md
    assert "provides" in md
    assert "graph-proj" in md


def test_export_evaluation_no_graph_no_relations_section():
    session = _make_session()
    project = _make_project(session, name="no-graph-proj", tags=[], topics=[])

    md = export_evaluation_markdown(session, project.id)

    assert "图谱关系" not in md


def test_export_evaluation_empty_fields_show_na():
    session = _make_session()
    project = _make_project(
        session,
        name="sparse",
        description=None,
        language=None,
        license_spdx=None,
    )

    md = export_evaluation_markdown(session, project.id)

    # description, language, license should show N/A
    assert "N/A" in md


# ── export_trial_markdown ──────────────────────────────────────────


def test_export_trial_returns_empty_for_missing_trial():
    session = _make_session()
    md = export_trial_markdown(session, trial_id=999)
    assert md == ""


def test_export_trial_basic():
    session = _make_session()
    project = _make_project(session, name="trial-proj")
    trial = _make_trial(
        session,
        project.id,
        owner="alice",
        status="claimed",
    )

    md = export_trial_markdown(session, trial.id)

    assert "# 试用记录: trial-proj" in md
    assert "https://github.com/test/trial-proj" in md
    assert "## 试用信息" in md
    assert "| 负责人 | alice |" in md
    assert "| 状态 | claimed |" in md


def test_export_trial_with_all_fields():
    session = _make_session()
    project = _make_project(session, name="full-trial")
    trial = _make_trial(
        session,
        project.id,
        owner="bob",
        status="demo_done",
        environment="Docker + Python 3.11",
        demo_url="https://demo.example.com",
        next_action="Prepare share",
        due_date=date(2026, 6, 1),
        trial_notes="Setup was smooth, ran all examples.",
        result_summary="Tool works well for our use case.",
        blockers=None,
    )

    md = export_trial_markdown(session, trial.id)

    assert "| 环境 | Docker + Python 3.11 |" in md
    assert "| Demo URL | https://demo.example.com |" in md
    assert "| 下一步 | Prepare share |" in md
    assert "2026-06-01" in md
    assert "## 试用笔记" in md
    assert "Setup was smooth" in md
    assert "## 结论" in md
    assert "Tool works well" in md


def test_export_trial_with_blockers():
    session = _make_session()
    project = _make_project(session, name="blocked-proj")
    trial = _make_trial(
        session,
        project.id,
        status="blocked",
        blockers="Missing GPU driver",
    )

    md = export_trial_markdown(session, trial.id)

    assert "## 阻碍" in md
    assert "Missing GPU driver" in md


def test_export_trial_no_optional_fields_no_extra_sections():
    session = _make_session()
    project = _make_project(session, name="minimal-trial")
    trial = _make_trial(
        session,
        project.id,
        trial_notes=None,
        result_summary=None,
        blockers=None,
    )

    md = export_trial_markdown(session, trial.id)

    assert "## 试用笔记" not in md
    assert "## 结论" not in md
    assert "## 阻碍" not in md


def test_export_trial_with_graph_relations():
    session = _make_session()
    project = _make_project(
        session,
        name="trial-graph-proj",
        tags=["RAG"],
    )
    build_project_graph(session, project)
    trial = _make_trial(session, project.id)

    md = export_trial_markdown(session, trial.id)

    assert "## 图谱关系" in md
    assert "belongs_to" in md


# ── export_share_markdown ──────────────────────────────────────────


def test_export_share_returns_empty_for_missing_share():
    session = _make_session()
    md = export_share_markdown(session, share_id=999)
    assert md == ""


def test_export_share_basic():
    session = _make_session()
    project = _make_project(session, name="share-proj")
    trial = _make_trial(session, project.id, status="demo_done")
    share = _make_share(
        session,
        trial.id,
        title="LangChain 试用分享",
        summary="Good for RAG pipelines.",
        shared_by="charlie",
    )

    md = export_share_markdown(session, share.id)

    assert "# 分享归档: LangChain 试用分享" in md
    assert "share-proj" in md
    assert "## 基本信息" in md
    assert "| 分享人 | charlie |" in md
    assert "## 摘要" in md
    assert "Good for RAG pipelines." in md


def test_export_share_with_all_sections():
    session = _make_session()
    project = _make_project(session, name="full-share")
    trial = _make_trial(session, project.id, status="shared")
    share = _make_share(
        session,
        trial.id,
        title="Full Share",
        summary="Summary text",
        key_findings="- Finding 1\n- Finding 2",
        reusable_patterns="Pattern A, Pattern B",
        applicable_scenarios="Scenario X",
        knowledge_doc_url="https://wiki.example.com/share1",
        shared_by="dave",
    )

    md = export_share_markdown(session, share.id)

    assert "## 核心发现" in md
    assert "Finding 1" in md
    assert "## 可复用模式" in md
    assert "Pattern A" in md
    assert "## 适用场景" in md
    assert "Scenario X" in md
    assert "https://wiki.example.com/share1" in md


def test_export_share_no_optional_sections():
    session = _make_session()
    project = _make_project(session, name="minimal-share")
    trial = _make_trial(session, project.id)
    share = _make_share(
        session,
        trial.id,
        title="Minimal",
        summary=None,
        key_findings=None,
        reusable_patterns=None,
        applicable_scenarios=None,
    )

    md = export_share_markdown(session, share.id)

    assert "## 摘要" not in md
    assert "## 核心发现" not in md
    assert "## 可复用模式" not in md
    assert "## 适用场景" not in md


def test_export_share_with_produced_graph_relation():
    session = _make_session()
    project = _make_project(session, name="share-graph-proj", tags=["Agent"])
    build_project_graph(session, project)
    trial = _make_trial(session, project.id, status="demo_done")
    share = _make_share(
        session,
        trial.id,
        title="Agent POC 分享",
        summary="Learned about agents.",
    )
    build_share_graph(session, share)

    md = export_share_markdown(session, share.id)

    assert "## 图谱关系" in md
    assert "produced" in md
    assert "Agent POC 分享" in md


def test_export_share_without_graph_no_relations_section():
    session = _make_session()
    project = _make_project(session, name="no-graph-share", tags=[], topics=[])
    trial = _make_trial(session, project.id)
    share = _make_share(session, trial.id, title="No Graph Share")

    md = export_share_markdown(session, share.id)

    assert "图谱关系" not in md


def test_export_share_trial_deleted_still_shows_basic():
    """When trial doesn't exist, share can still render basic info."""
    session = _make_session()
    share = Share(
        trial_id=999,  # non-existent trial
        title="Orphan Share",
        shared_by="eve",
    )
    session.add(share)
    session.commit()
    session.refresh(share)

    md = export_share_markdown(session, share.id)

    assert "# 分享归档: Orphan Share" in md
    assert "Unknown Project" in md
