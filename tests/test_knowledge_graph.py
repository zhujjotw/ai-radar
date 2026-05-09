"""Tests for T9 knowledge graph page — repository helpers and integration flows."""

from sqlmodel import Session, SQLModel, create_engine

from src.models import Project
from src.repositories import GraphRepository
from src.services.graph_builder import (
    add_dependency,
    build_project_graph,
    find_projects_by_capability,
    find_projects_by_dependency,
    find_projects_by_domain,
    get_project_ego_graph,
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
    language: str | None = None,
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
        language=language,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


# ── GraphRepository.list_node_names_by_type ───────────────────────────


class TestListNodeNamesByType:
    def test_returns_empty_when_no_nodes(self):
        session = _make_session()
        repo = GraphRepository(session)
        assert repo.list_node_names_by_type("Domain") == []

    def test_returns_sorted_domain_names(self):
        session = _make_session()
        repo = GraphRepository(session)
        project = _make_project(session, name="p1", tags=["RAG", "Agent"])
        build_project_graph(session, project)

        names = repo.list_node_names_by_type("Domain")
        assert names == ["Agent", "RAG"]

    def test_returns_capability_names(self):
        session = _make_session()
        repo = GraphRepository(session)
        project = _make_project(session, name="p1", topics=["embedding", "retrieval"])
        build_project_graph(session, project)

        names = repo.list_node_names_by_type("Capability")
        assert names == ["embedding", "retrieval"]

    def test_returns_dependency_names(self):
        session = _make_session()
        repo = GraphRepository(session)
        project = _make_project(session, name="p1")
        build_project_graph(session, project)
        add_dependency(session, project, "pytorch")
        add_dependency(session, project, "numpy")

        names = repo.list_node_names_by_type("Dependency")
        assert names == ["numpy", "pytorch"]

    def test_excludes_other_types(self):
        session = _make_session()
        repo = GraphRepository(session)
        project = _make_project(session, name="p1", tags=["Agent"], topics=["llm"])
        build_project_graph(session, project)

        domain_names = repo.list_node_names_by_type("Domain")
        capability_names = repo.list_node_names_by_type("Capability")
        assert "Agent" in domain_names
        assert "Agent" not in capability_names


# ── Integration: Ego Graph for Page Rendering ─────────────────────────


class TestEgoGraphForPage:
    def test_ego_graph_with_all_node_types(self):
        """Verify ego graph includes all 5 node types when present."""
        session = _make_session()
        project = _make_project(session, name="full-proj", tags=["Agent"], topics=["llm"])
        build_project_graph(session, project)
        add_dependency(session, project, "python")

        result = get_project_ego_graph(session, project.id)

        node_types = {n["node_type"] for n in result["nodes"]}
        assert "Project" in node_types
        assert "Domain" in node_types
        assert "Capability" in node_types
        assert "Dependency" in node_types

    def test_ego_graph_edge_relation_types(self):
        """Verify all expected relation types appear in ego graph."""
        session = _make_session()
        project = _make_project(session, name="rel-proj", tags=["RAG"], topics=["search"])
        build_project_graph(session, project)
        add_dependency(session, project, "transformers")

        result = get_project_ego_graph(session, project.id)

        edge_types = {e["relation_type"] for e in result["edges"]}
        assert "belongs_to" in edge_types
        assert "provides" in edge_types
        assert "depends_on" in edge_types

    def test_empty_project_shows_no_graph(self):
        """Project with no graph data returns empty nodes/edges."""
        session = _make_session()
        project = _make_project(session, name="empty-proj")

        result = get_project_ego_graph(session, project.id)
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_project_node_largest_in_graph(self):
        """Project node should have the largest size (25)."""
        session = _make_session()
        project = _make_project(session, name="big-proj", tags=["Eval"])
        build_project_graph(session, project)

        result = get_project_ego_graph(session, project.id)
        project_nodes = [n for n in result["nodes"] if n["node_type"] == "Project"]
        other_nodes = [n for n in result["nodes"] if n["node_type"] != "Project"]

        assert len(project_nodes) == 1
        assert project_nodes[0]["size"] == 25
        for other in other_nodes:
            assert other["size"] == 15

    def test_similar_to_appears_in_ego_graph(self):
        """similar_to edges appear in ego graph for both projects."""
        session = _make_session()
        from src.services.graph_builder import add_similar_to

        p1 = _make_project(session, name="sim-a", repo_full_name="t/sim-a")
        p2 = _make_project(session, name="sim-b", repo_full_name="t/sim-b")
        build_project_graph(session, p1)
        build_project_graph(session, p2)
        add_similar_to(session, p1, p2)

        result_a = get_project_ego_graph(session, p1.id)
        result_b = get_project_ego_graph(session, p2.id)

        edge_types_a = {e["relation_type"] for e in result_a["edges"]}
        edge_types_b = {e["relation_type"] for e in result_b["edges"]}
        assert "similar_to" in edge_types_a
        assert "similar_to" in edge_types_b


# ── Integration: Reverse Lookup for Page ──────────────────────────────


class TestReverseLookupForPage:
    def test_lookup_by_capability_returns_projects(self):
        session = _make_session()
        p1 = _make_project(session, name="cap-a", repo_full_name="t/cap-a", topics=["embedding"])
        p2 = _make_project(session, name="cap-b", repo_full_name="t/cap-b", topics=["embedding"])
        build_project_graph(session, p1)
        build_project_graph(session, p2)

        results = find_projects_by_capability(session, "embedding")
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"cap-a", "cap-b"}

    def test_lookup_by_dependency_returns_projects(self):
        session = _make_session()
        p1 = _make_project(session, name="dep-a", repo_full_name="t/dep-a")
        p2 = _make_project(session, name="dep-b", repo_full_name="t/dep-b")
        build_project_graph(session, p1)
        build_project_graph(session, p2)
        add_dependency(session, p1, "pytorch")
        add_dependency(session, p2, "pytorch")

        results = find_projects_by_dependency(session, "pytorch")
        assert len(results) == 2

    def test_lookup_by_domain_returns_projects(self):
        session = _make_session()
        p1 = _make_project(session, name="dom-a", repo_full_name="t/dom-a", tags=["Agent"])
        p2 = _make_project(session, name="dom-b", repo_full_name="t/dom-b", tags=["Agent"])
        build_project_graph(session, p1)
        build_project_graph(session, p2)

        results = find_projects_by_domain(session, "Agent")
        assert len(results) == 2

    def test_lookup_nonexistent_returns_empty(self):
        session = _make_session()
        assert find_projects_by_capability(session, "nonexistent") == []
        assert find_projects_by_dependency(session, "nonexistent") == []
        assert find_projects_by_domain(session, "nonexistent") == []

    def test_reverse_lookup_with_project_details(self):
        """Verify returned projects have details needed for the UI."""
        session = _make_session()
        project = _make_project(
            session,
            name="detail-proj",
            tags=["RAG"],
            stars=500,
            language="Python",
        )
        build_project_graph(session, project)

        results = find_projects_by_domain(session, "RAG")
        assert len(results) == 1
        assert results[0].stars == 500
        assert results[0].language == "Python"
        assert results[0].github_url.endswith("detail-proj")
