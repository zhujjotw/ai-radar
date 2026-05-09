"""End-to-end MVP flow test (T10).

Validates the complete lifecycle:
  1. Initialize database
  2. Seed baseline + candidate projects
  3. Filter + classify + score
  4. Create evaluation
  5. Create trial with status transitions
  6. Create share + build graph
  7. Query project ego graph
  8. Export Markdown
  9. Reverse lookups
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.models import Evaluation, Project, Share, Trial
from src.repositories import (
    EvaluationRepository,
    GraphRepository,
    ProjectRepository,
    ShareRepository,
    TrialRepository,
)
from src.services.classifier import classify_project
from src.services.graph_builder import (
    add_dependency,
    add_similar_to,
    build_project_graph,
    build_share_graph,
    find_projects_by_capability,
    find_projects_by_dependency,
    find_projects_by_domain,
    get_project_ego_graph,
)
from src.services.markdown_export import (
    export_evaluation_markdown,
    export_share_markdown,
    export_trial_markdown,
)
from src.services.project_filter import filter_project
from src.services.project_scorer import score_project


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        yield sess


def _utc(days_ago: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


def _make_project(**overrides) -> Project:
    defaults = {
        "github_url": "https://github.com/org/repo",
        "repo_full_name": "org/repo",
        "name": "Repo",
        "pool": "candidate",
        "source": "github_search",
        "stars": 5000,
        "forks": 500,
        "language": "Python",
        "topics": ["llm", "agent"],
        "tags": ["Agent"],
        "license": "MIT",
        "has_quickstart": True,
        "last_pushed_at": _utc(3),
    }
    defaults.update(overrides)
    return Project(**defaults)


# ── Test: Full MVP lifecycle ──────────────────────────────────────────


class TestMVPLifecycle:
    """Smoke test for the entire MVP flow from seed to export."""

    def test_full_flow(self, session: Session) -> None:
        project_repo = ProjectRepository(session)
        eval_repo = EvaluationRepository(session)
        trial_repo = TrialRepository(session)
        share_repo = ShareRepository(session)

        # ── Step 1: Seed projects ─────────────────────────────────────
        # 3 baseline + 2 candidate (one filtered out by low stars)
        p1 = project_repo.upsert(
            _make_project(
                repo_full_name="org/langchain",
                name="LangChain",
                pool="baseline",
                source="baseline",
                stars=95000,
                tags=["Agent", "RAG", "Workflow"],
                topics=["llm", "agent", "rag", "chains"],
            )
        )
        p2 = project_repo.upsert(
            _make_project(
                repo_full_name="org/openai-sdk",
                name="OpenAI SDK",
                pool="baseline",
                source="baseline",
                stars=25000,
                tags=["Inference"],
                topics=["openai", "llm", "api"],
            )
        )
        p3 = project_repo.upsert(
            _make_project(
                repo_full_name="org/crewai",
                name="crewAI",
                pool="candidate",
                source="github_search",
                stars=22000,
                tags=["Agent"],
                topics=["agent", "multi-agent"],
            )
        )
        p4 = project_repo.upsert(
            _make_project(
                repo_full_name="org/sglang",
                name="SGLang",
                pool="candidate",
                source="github_search",
                stars=8000,
                tags=["Inference"],
                topics=["inference", "llm"],
            )
        )
        p5 = project_repo.upsert(
            _make_project(
                repo_full_name="org/tiny-agent",
                name="TinyAgent",
                pool="candidate",
                source="github_search",
                stars=30,  # below threshold
                tags=["Agent"],
                topics=["agent"],
            )
        )

        assert project_repo.get(p1.id) is not None
        assert project_repo.get(p5.id) is not None

        # ── Step 2: Filter projects ───────────────────────────────────
        # High-star projects pass
        f1 = filter_project(stars=p1.stars, last_pushed_at=p1.last_pushed_at)
        assert f1["filter_status"] == "needs_review"

        f5 = filter_project(stars=p5.stars, last_pushed_at=p5.last_pushed_at)
        assert f5["filter_status"] == "filtered_out"
        assert "below threshold" in f5["filter_reason"]

        # Apply filter to p5
        p5.filter_status = f5["filter_status"]
        p5.filter_reason = f5["filter_reason"]
        project_repo.update(p5)

        # Verify filtered project is excluded from needs_review
        needs_review = project_repo.list(filter_status="needs_review")
        assert p5 not in needs_review

        # ── Step 3: Classify + Score ──────────────────────────────────
        tags_p3 = classify_project(
            name=p3.name,
            description=p3.description or "",
            topics=p3.topics,
        )
        assert "Agent" in tags_p3

        score_p3 = score_project(
            name=p3.name,
            description=p3.description or "",
            topics=p3.topics,
            stars=p3.stars,
            forks=p3.forks,
            license=p3.license,
            has_quickstart=p3.has_quickstart,
            tags=tags_p3,
        )
        assert score_p3["recommendation_score"] >= 1
        assert score_p3["relevance_score"] >= 1

        # ── Step 4: Create evaluation ─────────────────────────────────
        ev1 = eval_repo.create(
            Evaluation(
                project_id=p3.id,
                relevance_score=score_p3["relevance_score"],
                trialability_score=score_p3["trialability_score"],
                value_score=score_p3["value_score"],
                recommendation_score=score_p3["recommendation_score"],
                decision="try",
                decision_reason="Active multi-agent framework",
                evidence=score_p3["evidence"],
                evaluated_by="tester",
            )
        )
        assert ev1.id is not None
        assert ev1.decision == "try"

        ev_latest = eval_repo.get_latest_by_project(p3.id)
        assert ev_latest is not None
        assert ev_latest.decision == "try"

        # ── Step 5: Create trial + status transitions ─────────────────
        trial1 = trial_repo.create(
            Trial(
                project_id=p3.id,
                owner="alice",
                status="claimed",
                due_date=date.today() + timedelta(days=14),
            )
        )
        assert trial1.status == "claimed"

        # claimed -> running
        trial1.status = "running"
        trial1.environment = "Python 3.11 + conda"
        trial_repo.update(trial1)
        assert trial_repo.get(trial1.id).status == "running"

        # running -> demo_done (requires result_summary)
        trial1.status = "demo_done"
        trial1.result_summary = "CrewAI provides intuitive multi-agent orchestration"
        trial1.demo_url = "https://demo.example.com/crewai"
        trial_repo.update(trial1)
        assert trial_repo.get(trial1.id).status == "demo_done"

        # Create second trial (running state)
        trial2 = trial_repo.create(
            Trial(
                project_id=p4.id,
                owner="bob",
                status="running",
                due_date=date.today() + timedelta(days=7),
                environment="Docker + A100",
            )
        )
        assert trial_repo.list_by_owner("bob")[0].id == trial2.id

        # ── Step 6: Build graph + create share ────────────────────────
        build_project_graph(session, p1)
        build_project_graph(session, p2)
        build_project_graph(session, p3)
        build_project_graph(session, p4)

        # Add dependency: LangChain depends on OpenAI SDK
        add_dependency(session, p1, "openai-python")

        # Add similar_to: crewAI <-> LangChain
        add_similar_to(session, p1, p3, evidence="Both are agent frameworks")

        # Create share from trial1
        share1 = share_repo.create(
            Share(
                trial_id=trial1.id,
                title="CrewAI 试用分享",
                summary="CrewAI is effective for multi-agent orchestration.",
                key_findings="1. Intuitive YAML config\n2. Built-in tool integration",
                reusable_patterns="Agent role template pattern",
                applicable_scenarios="Structured multi-step tasks",
                shared_by="alice",
            )
        )
        assert share1.id is not None

        # Update trial status to shared
        trial1.status = "shared"
        trial_repo.update(trial1)

        # Build share graph
        build_share_graph(session, share1)

        # ── Step 7: Query ego graph ───────────────────────────────────
        ego = get_project_ego_graph(session, p1.id)
        assert len(ego["nodes"]) > 0
        assert len(ego["edges"]) > 0

        # Verify project node exists
        project_nodes = [n for n in ego["nodes"] if n["node_type"] == "Project"]
        assert len(project_nodes) >= 1

        # Verify domain edges
        relation_types = {e["relation_type"] for e in ego["edges"]}
        assert "belongs_to" in relation_types

        # ── Step 8: Export Markdown ────────────────────────────────────
        md_eval = export_evaluation_markdown(session, p3.id)
        assert "crewAI" in md_eval
        assert "try" in md_eval
        assert "评估记录" in md_eval

        md_trial = export_trial_markdown(session, trial1.id)
        assert "试用记录" in md_trial
        assert "alice" in md_trial

        md_share = export_share_markdown(session, share1.id)
        assert "CrewAI 试用分享" in md_share
        assert "核心发现" in md_share

        # ── Step 9: Reverse lookups ───────────────────────────────────
        # By domain
        agent_projects = find_projects_by_domain(session, "Agent")
        agent_names = {p.name for p in agent_projects}
        assert "LangChain" in agent_names or "crewAI" in agent_names

        # By dependency
        dep_projects = find_projects_by_dependency(session, "openai-python")
        dep_names = {p.name for p in dep_projects}
        assert "LangChain" in dep_names

        # By capability
        cap_projects = find_projects_by_capability(session, "multi-agent")
        cap_names = {p.name for p in cap_projects}
        assert "crewAI" in cap_names

        # ── Verify counts ─────────────────────────────────────────────
        all_projects = project_repo.list()
        assert len(all_projects) == 5

        all_trials = trial_repo.list_all()
        assert len(all_trials) == 2

        all_shares = share_repo.list_all()
        assert len(all_shares) == 1

        # ── Verify graph has TeamAsset node from share ────────────────
        ego_after_share = get_project_ego_graph(session, p3.id)
        node_types = {n["node_type"] for n in ego_after_share["nodes"]}
        assert "TeamAsset" in node_types
        relation_types_after = {e["relation_type"] for e in ego_after_share["edges"]}
        assert "produced" in relation_types_after


class TestSeedDemoDataScript:
    """Verify that seed_demo_data.py produces expected data."""

    def test_seed_produces_expected_counts(self, session: Session) -> None:
        """Import and run seed function, verify counts."""
        from scripts.seed_demo_data import seed

        summary = seed(session)

        assert summary["projects"] == 15  # 5 baseline + 10 candidate
        assert summary["evaluations"] == 2
        assert summary["trials"] == 2
        assert summary["shares"] == 1

        # Verify projects are queryable
        project_repo = ProjectRepository(session)
        all_projects = project_repo.list()
        assert len(all_projects) == 15

        baseline = project_repo.list(pool="baseline")
        assert len(baseline) == 5

        candidates = project_repo.list(pool="candidate")
        assert len(candidates) == 10

        # Verify some filtered out
        filtered = project_repo.list(filter_status="filtered_out")
        assert len(filtered) >= 2  # at least tiny-agent, old-toolkit, stale-inference

    def test_seed_has_graph_data(self, session: Session) -> None:
        """Verify graph data was created by seed."""
        from scripts.seed_demo_data import seed

        seed(session)

        graph_repo = GraphRepository(session)

        # LangChain should have ego graph with Domain nodes
        project_repo = ProjectRepository(session)
        langchain = project_repo.get_by_repo_full_name("langchain-ai/langchain")
        assert langchain is not None

        nodes, edges = graph_repo.get_one_hop(langchain.id)
        assert len(nodes) > 0
        assert len(edges) > 0

        # Should have Domain nodes
        node_types = {n.node_type for n in nodes}
        assert "Domain" in node_types

    def test_seed_share_has_team_asset(self, session: Session) -> None:
        """Verify share created TeamAsset graph node."""
        from scripts.seed_demo_data import seed

        seed(session)

        project_repo = ProjectRepository(session)
        graph_repo = GraphRepository(session)

        crewai = project_repo.get_by_repo_full_name("crewAIInc/crewAI")
        assert crewai is not None

        nodes, edges = graph_repo.get_one_hop(crewai.id)
        node_types = {n.node_type for n in nodes}
        assert "TeamAsset" in node_types

        # Should have produced edge
        edge_types = {e.relation_type for e in edges}
        assert "produced" in edge_types

    def test_seed_markdown_exports(self, session: Session) -> None:
        """Verify Markdown exports work with seeded data."""
        from scripts.seed_demo_data import seed

        seed(session)

        project_repo = ProjectRepository(session)
        share_repo = ShareRepository(session)
        trial_repo = TrialRepository(session)

        # Export evaluation markdown for crewAI
        crewai = project_repo.get_by_repo_full_name("crewAIInc/crewAI")
        md = export_evaluation_markdown(session, crewai.id)
        assert "crewAI" in md
        assert "评估" in md

        # Export share markdown
        shares = share_repo.list_all()
        assert len(shares) == 1
        md_share = export_share_markdown(session, shares[0].id)
        assert "CrewAI" in md_share

        # Export trial markdown for the demo_done trial
        trials = trial_repo.list_by_status("shared")
        assert len(trials) == 1
        md_trial = export_trial_markdown(session, trials[0].id)
        assert "试用记录" in md_trial
