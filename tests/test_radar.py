"""Tests for T6 radar page: repository extensions and helper logic."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.models import Evaluation, Project
from src.repositories import EvaluationRepository, ProjectRepository


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


# --- ProjectRepository.update ---


class TestProjectRepositoryUpdate:
    def test_update_filter_status(self, project_repo, session):
        project = project_repo.upsert(_make_project())
        project.filter_status = "override"
        project.filter_reason = "Team interest"
        result = project_repo.update(project)
        assert result.filter_status == "override"
        assert result.filter_reason == "Team interest"

        # Verify persistence
        fetched = project_repo.get(project.id)
        assert fetched.filter_status == "override"

    def test_update_pool(self, project_repo, session):
        project = project_repo.upsert(_make_project())
        project.pool = "baseline"
        result = project_repo.update(project)
        assert result.pool == "baseline"

    def test_update_preserves_id(self, project_repo, session):
        project = project_repo.upsert(_make_project())
        original_id = project.id
        project.stars = 9999
        result = project_repo.update(project)
        assert result.id == original_id
        assert result.stars == 9999


# --- ProjectRepository.list_with_options ---


class TestProjectRepositoryListWithOptions:
    def _seed_projects(self, project_repo):
        project_repo.upsert(
            _make_project(
                repo_full_name="org/agent-proj",
                name="Agent Project",
                pool="baseline",
                source="baseline",
                stars=1000,
                tags=["Agent", "RAG"],
                filter_status="needs_review",
            )
        )
        project_repo.upsert(
            _make_project(
                repo_full_name="org/rag-proj",
                name="RAG Project",
                pool="candidate",
                source="github_search",
                stars=200,
                tags=["RAG"],
                filter_status="passed",
            )
        )
        project_repo.upsert(
            _make_project(
                repo_full_name="org/infra-proj",
                name="Infra Project",
                pool="candidate",
                source="manual",
                stars=50,
                tags=["Inference"],
                filter_status="filtered_out",
            )
        )

    def test_list_all(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options()
        assert len(results) == 3

    def test_filter_by_pool(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(pool="baseline")
        assert len(results) == 1
        assert results[0].name == "Agent Project"

    def test_filter_by_source(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(source="github_search")
        assert len(results) == 1
        assert results[0].name == "RAG Project"

    def test_filter_by_filter_status(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(filter_status="filtered_out")
        assert len(results) == 1
        assert results[0].name == "Infra Project"

    def test_filter_by_tag(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(tag="RAG")
        assert len(results) == 2
        names = {p.name for p in results}
        assert "Agent Project" in names
        assert "RAG Project" in names

    def test_filter_by_tag_no_match(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(tag="Workflow")
        assert len(results) == 0

    def test_combined_filters(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(pool="candidate", source="manual")
        assert len(results) == 1
        assert results[0].name == "Infra Project"

    def test_order_by_stars_desc(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(order_by="stars", order_desc=True)
        assert results[0].stars == 1000
        assert results[-1].stars == 50

    def test_order_by_stars_asc(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options(order_by="stars", order_desc=False)
        assert results[0].stars == 50
        assert results[-1].stars == 1000

    def test_default_order_by_first_seen_desc(self, project_repo):
        self._seed_projects(project_repo)
        results = project_repo.list_with_options()
        assert len(results) == 3
        # Default order is first_seen_at desc (newest first)


# --- ProjectRepository.get_all_tags ---


class TestProjectRepositoryGetAllTags:
    def test_returns_sorted_unique_tags(self, project_repo):
        project_repo.upsert(
            _make_project(
                repo_full_name="a/b",
                tags=["Agent", "RAG"],
            )
        )
        project_repo.upsert(
            _make_project(
                repo_full_name="c/d",
                tags=["RAG", "Inference"],
            )
        )
        project_repo.upsert(
            _make_project(
                repo_full_name="e/f",
                tags=[],
            )
        )
        tags = project_repo.get_all_tags()
        assert tags == ["Agent", "Inference", "RAG"]

    def test_empty_db(self, project_repo):
        tags = project_repo.get_all_tags()
        assert tags == []


# --- EvaluationRepository.get_latest_by_project ---


class TestEvaluationRepositoryGetLatest:
    def test_returns_none_when_no_evaluation(self, evaluation_repo, project_repo):
        project = project_repo.upsert(_make_project())
        result = evaluation_repo.get_latest_by_project(project.id)
        assert result is None

    def test_returns_evaluation_when_one(self, evaluation_repo, project_repo):
        project = project_repo.upsert(_make_project())
        evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="watch",
                recommendation_score=7,
            )
        )
        result = evaluation_repo.get_latest_by_project(project.id)
        assert result is not None
        assert result.decision == "watch"
        assert result.recommendation_score == 7

    def test_returns_latest_when_multiple(self, evaluation_repo, project_repo):
        project = project_repo.upsert(_make_project())
        evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="watch",
                recommendation_score=5,
            )
        )
        evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="try",
                recommendation_score=8,
            )
        )
        result = evaluation_repo.get_latest_by_project(project.id)
        assert result is not None
        assert result.decision == "try"
        assert result.recommendation_score == 8


# --- EvaluationRepository.update ---


class TestEvaluationRepositoryUpdate:
    def test_update_decision(self, evaluation_repo, project_repo):
        project = project_repo.upsert(_make_project())
        ev = evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="watch",
            )
        )
        ev.decision = "try"
        ev.decision_reason = "Looks promising"
        updated = evaluation_repo.update(ev)
        assert updated.decision == "try"
        assert updated.decision_reason == "Looks promising"

    def test_update_preserves_id(self, evaluation_repo, project_repo):
        project = project_repo.upsert(_make_project())
        ev = evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="watch",
            )
        )
        original_id = ev.id
        ev.recommendation_score = 9
        updated = evaluation_repo.update(ev)
        assert updated.id == original_id
        assert updated.recommendation_score == 9


# --- Integration: decision + filter override flow ---


class TestRadarFlowIntegration:
    def test_set_decision_creates_evaluation(self, project_repo, evaluation_repo):
        project = project_repo.upsert(_make_project())
        # Simulate radar page setting a decision
        new_eval = Evaluation(
            project_id=project.id,
            decision="try",
            decision_reason="High potential for our stack",
        )
        created = evaluation_repo.create(new_eval)
        assert created.id is not None

        latest = evaluation_repo.get_latest_by_project(project.id)
        assert latest is not None
        assert latest.decision == "try"

    def test_update_existing_decision(self, project_repo, evaluation_repo):
        project = project_repo.upsert(_make_project())
        ev = evaluation_repo.create(
            Evaluation(
                project_id=project.id,
                decision="watch",
            )
        )
        ev.decision = "reject"
        ev.decision_reason = "Not a good fit"
        evaluation_repo.update(ev)

        latest = evaluation_repo.get_latest_by_project(project.id)
        assert latest.decision == "reject"

    def test_override_filter_status(self, project_repo):
        project = project_repo.upsert(
            _make_project(
                filter_status="filtered_out",
                filter_reason="Stars 50 below threshold 200",
            )
        )
        assert project.filter_status == "filtered_out"

        # Override
        project.filter_status = "override"
        project.filter_reason = "Team is interested in this"
        updated = project_repo.update(project)
        assert updated.filter_status == "override"

    def test_remove_override(self, project_repo):
        project = project_repo.upsert(
            _make_project(
                filter_status="override",
                filter_reason="Manual override",
            )
        )
        project.filter_status = "needs_review"
        project.filter_reason = None
        updated = project_repo.update(project)
        assert updated.filter_status == "needs_review"
        assert updated.filter_reason is None

    def test_filter_by_decision_joins_evaluation(self, project_repo, evaluation_repo):
        p1 = project_repo.upsert(
            _make_project(
                repo_full_name="a/watched",
                name="Watched Project",
            )
        )
        p2 = project_repo.upsert(
            _make_project(
                repo_full_name="a/tried",
                name="Tried Project",
            )
        )
        evaluation_repo.create(Evaluation(project_id=p1.id, decision="watch"))
        evaluation_repo.create(Evaluation(project_id=p2.id, decision="try"))

        results = project_repo.list_with_options(decision="try")
        assert len(results) == 1
        assert results[0].name == "Tried Project"

    def test_list_with_options_empty_result(self, project_repo):
        results = project_repo.list_with_options(pool="nonexistent")
        assert results == []
