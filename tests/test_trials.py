"""Tests for T7 trial page: repository extensions and trial management flows."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.models import Evaluation, Project, Trial
from src.repositories import EvaluationRepository, ProjectRepository, TrialRepository


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
def evaluation_repo(session):
    return EvaluationRepository(session)


@pytest.fixture
def trial_repo(session):
    return TrialRepository(session)


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
        "status": "claimed",
    }
    defaults.update(overrides)
    return Trial(**defaults)


# --- TrialRepository.get ---


class TestTrialRepositoryGet:
    def test_get_existing_trial(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        result = trial_repo.get(trial.id)
        assert result is not None
        assert result.id == trial.id
        assert result.owner == "alice"

    def test_get_nonexistent_trial(self, trial_repo):
        result = trial_repo.get(9999)
        assert result is None


# --- TrialRepository.update ---


class TestTrialRepositoryUpdate:
    def test_update_trial_fields(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        trial.status = "running"
        trial.environment = "Docker"
        trial.trial_notes = "Initial setup complete"
        updated = trial_repo.update(trial)
        assert updated.status == "running"
        assert updated.environment == "Docker"
        assert updated.trial_notes == "Initial setup complete"

    def test_update_preserves_id(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        original_id = trial.id
        trial.result_summary = "Works well"
        updated = trial_repo.update(trial)
        assert updated.id == original_id
        assert updated.result_summary == "Works well"

    def test_update_result_summary(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        trial.result_summary = "Fast inference, good accuracy"
        trial.demo_url = "https://demo.example.com"
        updated = trial_repo.update(trial)
        assert updated.result_summary == "Fast inference, good accuracy"
        assert updated.demo_url == "https://demo.example.com"

    def test_update_next_action(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        trial.next_action = "Prepare team presentation"
        updated = trial_repo.update(trial)
        assert updated.next_action == "Prepare team presentation"


# --- TrialRepository.update_status ---


class TestTrialRepositoryUpdateStatus:
    def test_update_status_basic(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id))
        updated = trial_repo.update_status(trial.id, "running")
        assert updated.status == "running"

    def test_update_status_with_blockers(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="running"))
        updated = trial_repo.update_status(trial.id, "blocked", blockers="Missing GPU drivers")
        assert updated.status == "blocked"
        assert updated.blockers == "Missing GPU drivers"

    def test_update_status_nonexistent_raises(self, trial_repo):
        with pytest.raises(ValueError, match="Trial 9999 not found"):
            trial_repo.update_status(9999, "running")


# --- TrialRepository.list_by_project ---


class TestTrialRepositoryListByProject:
    def test_returns_trials_for_project(self, trial_repo, project_repo):
        p1 = project_repo.upsert(_make_project(repo_full_name="a/proj1"))
        p2 = project_repo.upsert(_make_project(repo_full_name="a/proj2"))
        trial_repo.create(_make_trial(p1.id, owner="alice"))
        trial_repo.create(_make_trial(p1.id, owner="bob"))
        trial_repo.create(_make_trial(p2.id, owner="charlie"))

        results = trial_repo.list_by_project(p1.id)
        assert len(results) == 2
        owners = {t.owner for t in results}
        assert owners == {"alice", "bob"}

    def test_returns_empty_for_no_trials(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        results = trial_repo.list_by_project(project.id)
        assert results == []


# --- TrialRepository.list_by_status ---


class TestTrialRepositoryListByStatus:
    def test_returns_trials_with_given_status(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial_repo.create(_make_trial(project.id, status="claimed"))
        trial_repo.create(_make_trial(project.id, status="running"))
        trial_repo.create(_make_trial(project.id, status="blocked"))

        claimed = trial_repo.list_by_status("claimed")
        assert len(claimed) == 1
        assert claimed[0].status == "claimed"

    def test_returns_empty_for_nonexistent_status(self, trial_repo):
        results = trial_repo.list_by_status("nonexistent")
        assert results == []


# --- TrialRepository.list_by_owner ---


class TestTrialRepositoryListByOwner:
    def test_returns_trials_for_owner(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial_repo.create(_make_trial(project.id, owner="alice"))
        trial_repo.create(_make_trial(project.id, owner="bob"))
        trial_repo.create(_make_trial(project.id, owner="alice"))

        alice_trials = trial_repo.list_by_owner("alice")
        assert len(alice_trials) == 2
        for t in alice_trials:
            assert t.owner == "alice"


# --- TrialRepository.list_all ---


class TestTrialRepositoryListAll:
    def test_returns_all_trials(self, trial_repo, project_repo):
        project = project_repo.upsert(_make_project())
        trial_repo.create(_make_trial(project.id, owner="alice"))
        trial_repo.create(_make_trial(project.id, owner="bob"))
        results = trial_repo.list_all()
        assert len(results) == 2

    def test_returns_empty_when_none(self, trial_repo):
        results = trial_repo.list_all()
        assert results == []


# --- Integration: Trial lifecycle flows ---


class TestTrialLifecycleIntegration:
    def test_claim_to_running(self, trial_repo, project_repo, evaluation_repo):
        """Full flow: project evaluated as try → claimed → running."""
        project = project_repo.upsert(_make_project())
        evaluation_repo.create(Evaluation(project_id=project.id, decision="try"))

        # Claim
        trial = trial_repo.create(
            Trial(
                project_id=project.id,
                owner="alice",
                status="claimed",
            )
        )
        assert trial.status == "claimed"

        # Transition to running
        trial.status = "running"
        trial.environment = "Docker on M2 Mac"
        updated = trial_repo.update(trial)
        assert updated.status == "running"
        assert updated.environment == "Docker on M2 Mac"

    def test_running_to_blocked_to_running(self, trial_repo, project_repo):
        """Trial can be blocked and then resumed."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="running"))

        # Blocked
        trial.status = "blocked"
        trial.blockers = "CUDA version mismatch"
        trial_repo.update(trial)

        fetched = trial_repo.get(trial.id)
        assert fetched.status == "blocked"
        assert fetched.blockers == "CUDA version mismatch"

        # Resume
        fetched.status = "running"
        fetched.blockers = None
        trial_repo.update(fetched)

        resumed = trial_repo.get(trial.id)
        assert resumed.status == "running"
        assert resumed.blockers is None

    def test_running_to_demo_done_requires_result_summary(self, trial_repo, project_repo):
        """Demo done requires result summary (business rule)."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="running"))

        # Try demo_done without result_summary — should not be allowed in UI logic
        assert trial.result_summary is None

        # Add result summary first
        trial.result_summary = "Fast and accurate, good fit for our use case"
        trial_repo.update(trial)

        # Now transition to demo_done
        trial.status = "demo_done"
        updated = trial_repo.update(trial)
        assert updated.status == "demo_done"
        assert updated.result_summary == "Fast and accurate, good fit for our use case"

    def test_demo_done_to_shared(self, trial_repo, project_repo):
        """Trial can go from demo_done to shared (T8 will use this)."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(
            _make_trial(
                project.id,
                status="demo_done",
                result_summary="Excellent tool",
            )
        )

        trial.status = "shared"
        updated = trial_repo.update(trial)
        assert updated.status == "shared"

    def test_dropped_with_reason(self, trial_repo, project_repo):
        """Dropped trials can record a reason in trial_notes."""
        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(_make_trial(project.id, status="claimed"))

        trial.status = "dropped"
        trial.trial_notes = "[Dropped: No longer relevant to current roadmap]"
        updated = trial_repo.update(trial)
        assert updated.status == "dropped"
        assert "No longer relevant" in updated.trial_notes

    def test_multiple_trials_per_project(self, trial_repo, project_repo):
        """A project can have multiple trials (different owners)."""
        project = project_repo.upsert(_make_project())
        t1 = trial_repo.create(_make_trial(project.id, owner="alice"))
        t2 = trial_repo.create(_make_trial(project.id, owner="bob"))

        trials = trial_repo.list_by_project(project.id)
        assert len(trials) == 2

        # One can be running while another is blocked
        t1.status = "running"
        trial_repo.update(t1)
        t2.status = "blocked"
        t2.blockers = "No access to GPU cluster"
        trial_repo.update(t2)

        running = trial_repo.list_by_status("running")
        blocked = trial_repo.list_by_status("blocked")
        assert len(running) == 1
        assert len(blocked) == 1

    def test_trial_with_all_fields(self, trial_repo, project_repo):
        """Create and update a trial with all fields populated."""
        from datetime import date

        project = project_repo.upsert(_make_project())
        trial = trial_repo.create(
            Trial(
                project_id=project.id,
                owner="alice",
                status="claimed",
                due_date=date(2026, 6, 1),
                environment="AWS EC2 g4dn.xlarge",
            )
        )
        assert trial.due_date == date(2026, 6, 1)
        assert trial.environment == "AWS EC2 g4dn.xlarge"

        # Update with all fields
        trial.status = "demo_done"
        trial.demo_url = "https://demo.example.com/langchain-trial"
        trial.trial_notes = "Tested with 3 use cases, all passed"
        trial.result_summary = "Excellent RAG library, easy to integrate"
        trial.next_action = "Prepare knowledge sharing session"
        updated = trial_repo.update(trial)

        assert updated.demo_url == "https://demo.example.com/langchain-trial"
        assert updated.result_summary == "Excellent RAG library, easy to integrate"
        assert updated.next_action == "Prepare knowledge sharing session"

    def test_end_to_end_trial_flow(self, trial_repo, project_repo, evaluation_repo):
        """Complete flow: evaluate → try → claim → run → demo_done."""
        # 1. Project exists
        project = project_repo.upsert(
            _make_project(
                name="LangGraph",
                repo_full_name="langchain-ai/langgraph",
            )
        )

        # 2. Evaluate as "try"
        evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="try",
                recommendation_score=8,
            )
        )

        # Verify it shows up as "try" project
        try_projects = project_repo.list_with_options(decision="try")
        assert len(try_projects) == 1
        assert try_projects[0].name == "LangGraph"

        # 3. Claim
        trial = trial_repo.create(
            Trial(
                project_id=project.id,
                owner="alice",
                status="claimed",
            )
        )

        # 4. Start running
        trial.status = "running"
        trial.environment = "Docker"
        trial_repo.update(trial)

        # 5. Record results
        trial.result_summary = "Powerful agent framework"
        trial.demo_url = "https://demo.example.com/langgraph"
        trial_repo.update(trial)

        # 6. Mark demo_done
        trial.status = "demo_done"
        trial_repo.update(trial)

        # Verify final state
        final = trial_repo.get(trial.id)
        assert final.status == "demo_done"
        assert final.result_summary == "Powerful agent framework"
        assert final.demo_url == "https://demo.example.com/langgraph"

        # Verify we can query for demo_done trials
        demo_done = trial_repo.list_by_status("demo_done")
        assert len(demo_done) == 1
