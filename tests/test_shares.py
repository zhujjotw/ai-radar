"""Tests for T8 share archive page: repository extensions and share management flows."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.models import Project, Share, Trial
from src.repositories import (
    GraphRepository,
    ProjectRepository,
    ShareRepository,
    TrialRepository,
)
from src.services.graph_builder import build_project_graph, build_share_graph
from src.services.markdown_export import export_share_markdown


@pytest.fixture
def engine():
    """In-memory SQLite engine for tests."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture
def session(engine):
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def project_repo(session):
    return ProjectRepository(session)


@pytest.fixture
def trial_repo(session):
    return TrialRepository(session)


@pytest.fixture
def share_repo(session):
    return ShareRepository(session)


@pytest.fixture
def graph_repo(session):
    return GraphRepository(session)


def _make_project(**overrides) -> Project:
    defaults = {
        "github_url": "https://github.com/test/project",
        "repo_full_name": "test/project",
        "name": "Test Project",
        "pool": "candidate",
        "source": "manual",
        "stars": 500,
        "tags": ["Agent"],
    }
    defaults.update(overrides)
    return Project(**defaults)


def _make_trial(project_id: int, **overrides) -> Trial:
    defaults = {
        "project_id": project_id,
        "owner": "alice",
        "status": "demo_done",
        "result_summary": "Excellent tool for agent orchestration",
    }
    defaults.update(overrides)
    return Trial(**defaults)


def _make_share(trial_id: int, **overrides) -> Share:
    defaults = {
        "trial_id": trial_id,
        "title": "LangGraph Trial Report",
        "summary": "Powerful agent framework",
        "key_findings": "Easy to compose agents",
        "reusable_patterns": "Graph-based workflow pattern",
        "applicable_scenarios": "Multi-step agent pipelines",
        "shared_by": "alice",
    }
    defaults.update(overrides)
    return Share(**defaults)


# --- ShareRepository.get ---


class TestShareRepositoryGet:
    def test_get_existing_share(self, share_repo, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share = share_repo.create(_make_share(trial.id))
        result = share_repo.get(share.id)
        assert result is not None
        assert result.id == share.id
        assert result.title == "LangGraph Trial Report"

    def test_get_nonexistent_share(self, share_repo):
        result = share_repo.get(9999)
        assert result is None


# --- ShareRepository.get_by_trial_id ---


class TestShareRepositoryGetByTrialId:
    def test_returns_share_for_trial(self, share_repo, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share = share_repo.create(_make_share(trial.id))
        result = share_repo.get_by_trial_id(trial.id)
        assert result is not None
        assert result.id == share.id

    def test_returns_none_for_trial_without_share(self, share_repo, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        result = share_repo.get_by_trial_id(trial.id)
        assert result is None


# --- ShareRepository.list_by_shared_by ---


class TestShareRepositoryListBySharedBy:
    def test_returns_shares_for_person(self, share_repo, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share_repo.create(_make_share(trial.id, shared_by="alice"))
        share_repo.create(_make_share(trial.id, shared_by="bob", title="Bob's Report"))

        alice_shares = share_repo.list_by_shared_by("alice")
        assert len(alice_shares) == 1
        assert alice_shares[0].shared_by == "alice"

    def test_returns_empty_for_unknown_person(self, share_repo):
        results = share_repo.list_by_shared_by("nobody")
        assert results == []


# --- ShareRepository.list_all ---


class TestShareRepositoryListAll:
    def test_returns_all_shares(self, share_repo, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share_repo.create(_make_share(trial.id, title="Share 1"))
        share_repo.create(_make_share(trial.id, title="Share 2"))
        results = share_repo.list_all()
        assert len(results) == 2

    def test_returns_empty_when_none(self, share_repo):
        results = share_repo.list_all()
        assert results == []


# --- Integration: Share creation flow ---


class TestShareCreationIntegration:
    def test_create_share_updates_trial_to_shared(self, share_repo, trial_repo, project_repo):
        """Creating a share should update the trial status to 'shared'."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="demo_done"))
        assert trial.status == "demo_done"

        share_repo.create(_make_share(trial.id))

        # Simulate the T8 page logic: update trial to shared
        trial.status = "shared"
        trial_repo.update(trial)

        updated_trial = trial_repo.get(trial.id)
        assert updated_trial.status == "shared"

    def test_share_creates_team_asset_graph(self, share_repo, trial_repo, project_repo, session):
        """build_share_graph creates TeamAsset node and produced edge."""
        project = project_repo.upsert(_make_project(name="LangGraph"))
        build_project_graph(session, project)

        trial = trial_repo.create(_make_trial(project.id, status="demo_done"))
        share = share_repo.create(_make_share(trial.id))

        build_share_graph(session, share)

        # Verify TeamAsset node exists
        graph_repo = GraphRepository(session)
        nodes, edges = graph_repo.get_one_hop(project.id)

        # Should find at least the produced edge
        produced_edges = [e for e in edges if e.relation_type == "produced"]
        assert len(produced_edges) >= 1

        # Should find TeamAsset node
        team_asset_nodes = [n for n in nodes if n.node_type == "TeamAsset"]
        assert len(team_asset_nodes) >= 1
        assert team_asset_nodes[0].name == share.title

    def test_share_prevents_duplicate_for_same_trial(self, share_repo, trial_repo, project_repo):
        """get_by_trial_id returns existing share, preventing duplicates."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share_repo.create(_make_share(trial.id))

        # Check if share already exists for this trial
        existing = share_repo.get_by_trial_id(trial.id)
        assert existing is not None  # Should find existing share

    def test_demo_done_trial_not_shown_after_share(self, trial_repo, project_repo, share_repo):
        """After sharing, trial no longer appears in demo_done list."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="demo_done"))

        # Initially in demo_done
        demo_done = trial_repo.list_by_status("demo_done")
        assert len(demo_done) == 1

        # Create share and update trial
        share_repo.create(_make_share(trial.id))
        trial.status = "shared"
        trial_repo.update(trial)

        # No longer in demo_done
        demo_done = trial_repo.list_by_status("demo_done")
        assert len(demo_done) == 0

        # Now in shared
        shared = trial_repo.list_by_status("shared")
        assert len(shared) == 1


# --- Integration: Markdown export from share ---


class TestShareMarkdownExport:
    def test_export_share_markdown_with_all_fields(
        self, share_repo, trial_repo, project_repo, session
    ):
        """Markdown export includes all share fields."""
        project = project_repo.upsert(_make_project(name="LangGraph"))
        build_project_graph(session, project)

        trial = trial_repo.create(_make_trial(project.id, status="demo_done"))
        share = share_repo.create(_make_share(trial.id))

        build_share_graph(session, share)

        md = export_share_markdown(session, share.id)
        assert md != ""
        assert "LangGraph Trial Report" in md
        assert "Powerful agent framework" in md
        assert "Easy to compose agents" in md
        assert "Graph-based workflow pattern" in md
        assert "Multi-step agent pipelines" in md
        assert "alice" in md
        assert "produced" in md

    def test_export_share_markdown_minimal(self, share_repo, trial_repo, project_repo, session):
        """Markdown export works with only required fields."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        share = share_repo.create(Share(trial_id=trial.id, title="Minimal Share"))

        md = export_share_markdown(session, share.id)
        assert md != ""
        assert "Minimal Share" in md

    def test_export_share_markdown_nonexistent(self, session):
        """Returns empty string for nonexistent share."""
        md = export_share_markdown(session, 9999)
        assert md == ""


# --- Integration: End-to-end share flow ---


class TestEndToEndShareFlow:
    def test_full_share_flow(self, trial_repo, project_repo, share_repo, session):
        """Complete flow: project → trial → demo_done → share → graph → markdown."""
        # 1. Project exists with graph
        project = project_repo.upsert(
            _make_project(
                name="CrewAI",
                repo_full_name="crewai/crewai",
                tags=["Agent", "Workflow"],
            )
        )
        build_project_graph(session, project)

        # 2. Trial is demo_done
        trial = trial_repo.create(
            Trial(
                project_id=project.id,
                owner="bob",
                status="demo_done",
                result_summary="Great multi-agent orchestration",
                demo_url="https://demo.crewai.com",
            )
        )

        # 3. Create share
        share = share_repo.create(
            Share(
                trial_id=trial.id,
                title="CrewAI Multi-Agent Trial",
                summary="CrewAI enables building multi-agent systems",
                key_findings="Role-based agent design works well",
                reusable_patterns="Agent crew composition pattern",
                applicable_scenarios="Complex multi-step workflows",
                shared_by="bob",
            )
        )

        # 4. Update trial to shared
        trial.status = "shared"
        trial_repo.update(trial)

        # 5. Build share graph
        build_share_graph(session, share)

        # 6. Verify trial is shared
        assert trial_repo.get(trial.id).status == "shared"

        # 7. Verify graph has produced edge
        graph_repo = GraphRepository(session)
        nodes, edges = graph_repo.get_one_hop(project.id)
        produced_edges = [e for e in edges if e.relation_type == "produced"]
        assert len(produced_edges) >= 1
        team_asset = [n for n in nodes if n.node_type == "TeamAsset"]
        assert len(team_asset) >= 1
        assert team_asset[0].name == "CrewAI Multi-Agent Trial"

        # 8. Verify Markdown export
        md = export_share_markdown(session, share.id)
        assert "CrewAI Multi-Agent Trial" in md
        assert "bob" in md
        assert "produced" in md
        assert "Agent" in md or "belongs_to" in md

    def test_multiple_shares_different_trials(self, trial_repo, project_repo, share_repo):
        """Multiple projects can each have their own share records."""
        p1 = project_repo.upsert(_make_project(name="Proj A", repo_full_name="a/proj-a"))
        p2 = project_repo.upsert(_make_project(name="Proj B", repo_full_name="b/proj-b"))

        t1 = trial_repo.create(_make_trial(p1.id, owner="alice"))
        t2 = trial_repo.create(_make_trial(p2.id, owner="bob"))

        share_repo.create(_make_share(t1.id, title="Share A", shared_by="alice"))
        share_repo.create(_make_share(t2.id, title="Share B", shared_by="bob"))

        all_shares = share_repo.list_all()
        assert len(all_shares) == 2

        alice_shares = share_repo.list_by_shared_by("alice")
        assert len(alice_shares) == 1
        assert alice_shares[0].title == "Share A"
