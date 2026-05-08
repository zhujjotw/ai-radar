"""Tests for T4 graph_builder module."""

from sqlmodel import Session, SQLModel, create_engine

from src.db import get_session
from src.models import GraphEdge, GraphNode, Project, Share, Trial
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
) -> Project:
    """Helper to create and persist a Project."""
    project = Project(
        github_url=f"https://github.com/test/{name}",
        repo_full_name=repo_full_name or f"test/{name}",
        name=name,
        description=description,
        tags=tags or [],
        topics=topics or [],
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


# ── Build Project Graph ────────────────────────────────────────────


class TestBuildProjectGraph:
    """Tests for build_project_graph."""

    def test_creates_project_node(self):
        session = _make_session()
        project = _make_project(session, name="langchain")
        build_project_graph(session, project)

        nodes = session.exec(
            __import__("sqlmodel").select(GraphNode).where(GraphNode.node_type == "Project")
        ).all()
        assert len(nodes) == 1
        assert nodes[0].name == "langchain"
        assert nodes[0].ref_id == project.id

    def test_creates_domain_nodes_from_tags(self):
        session = _make_session()
        project = _make_project(session, tags=["Agent", "RAG"])
        build_project_graph(session, project)

        domain_nodes = session.exec(
            __import__("sqlmodel").select(GraphNode).where(GraphNode.node_type == "Domain")
        ).all()
        domain_names = {n.name for n in domain_nodes}
        assert domain_names == {"Agent", "RAG"}

    def test_creates_capability_nodes_from_topics(self):
        session = _make_session()
        project = _make_project(session, topics=["llm", "agent"])
        build_project_graph(session, project)

        cap_nodes = session.exec(
            __import__("sqlmodel").select(GraphNode).where(GraphNode.node_type == "Capability")
        ).all()
        cap_names = {n.name for n in cap_nodes}
        assert cap_names == {"llm", "agent"}

    def test_creates_belongs_to_edges(self):
        session = _make_session()
        project = _make_project(session, tags=["Agent"])
        build_project_graph(session, project)

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "belongs_to")
        ).all()
        assert len(edges) == 1
        assert edges[0].relation_type == "belongs_to"

    def test_creates_provides_edges(self):
        session = _make_session()
        project = _make_project(session, topics=["rag"])
        build_project_graph(session, project)

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "provides")
        ).all()
        assert len(edges) == 1

    def test_idempotent_no_duplicates(self):
        """Calling build_project_graph twice should not create duplicate nodes/edges."""
        session = _make_session()
        project = _make_project(session, tags=["Agent"], topics=["llm"])
        build_project_graph(session, project)
        build_project_graph(session, project)

        nodes = session.exec(__import__("sqlmodel").select(GraphNode)).all()
        edges = session.exec(__import__("sqlmodel").select(GraphEdge)).all()
        # 1 Project + 1 Domain + 1 Capability = 3 nodes
        assert len(nodes) == 3
        # 1 belongs_to + 1 provides = 2 edges
        assert len(edges) == 2

    def test_empty_tags_and_topics(self):
        session = _make_session()
        project = _make_project(session, tags=[], topics=[])
        build_project_graph(session, project)

        # Only the Project node should be created
        nodes = session.exec(__import__("sqlmodel").select(GraphNode)).all()
        assert len(nodes) == 1
        assert nodes[0].node_type == "Project"


# ── Add Dependency ─────────────────────────────────────────────────


class TestAddDependency:
    def test_creates_dependency_node_and_edge(self):
        session = _make_session()
        project = _make_project(session, name="my-app")
        add_dependency(session, project, "python")

        dep_nodes = session.exec(
            __import__("sqlmodel").select(GraphNode).where(GraphNode.node_type == "Dependency")
        ).all()
        assert len(dep_nodes) == 1
        assert dep_nodes[0].name == "python"

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "depends_on")
        ).all()
        assert len(edges) == 1

    def test_created_by_recorded(self):
        session = _make_session()
        project = _make_project(session)
        add_dependency(session, project, "nodejs", created_by="alice")

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "depends_on")
        ).all()
        assert edges[0].created_by == "alice"


# ── Add Similar To ─────────────────────────────────────────────────


class TestAddSimilarTo:
    def test_creates_similar_edge(self):
        session = _make_session()
        a = _make_project(session, name="project-a", repo_full_name="test/a")
        b = _make_project(session, name="project-b", repo_full_name="test/b")
        add_similar_to(session, a, b)

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "similar_to")
        ).all()
        assert len(edges) == 1

    def test_similar_edge_with_evidence(self):
        session = _make_session()
        a = _make_project(session, name="p1", repo_full_name="t/p1")
        b = _make_project(session, name="p2", repo_full_name="t/p2")
        add_similar_to(session, a, b, evidence="Both are RAG frameworks")

        edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "similar_to")
        ).all()
        assert edges[0].evidence == "Both are RAG frameworks"


# ── Build Share Graph ──────────────────────────────────────────────


class TestBuildShareGraph:
    def test_creates_team_asset_and_produced_edge(self):
        session = _make_session()
        project = _make_project(session, name="shared-project")
        build_project_graph(session, project)

        trial = Trial(project_id=project.id, owner="alice", status="demo_done")
        session.add(trial)
        session.commit()
        session.refresh(trial)

        share = Share(
            trial_id=trial.id,
            title="LangChain Trial Report",
            summary="Key findings from trial",
        )
        session.add(share)
        session.commit()
        session.refresh(share)

        build_share_graph(session, share)

        team_nodes = session.exec(
            __import__("sqlmodel").select(GraphNode).where(GraphNode.node_type == "TeamAsset")
        ).all()
        assert len(team_nodes) == 1
        assert team_nodes[0].name == "LangChain Trial Report"

        produced_edges = session.exec(
            __import__("sqlmodel").select(GraphEdge).where(GraphEdge.relation_type == "produced")
        ).all()
        assert len(produced_edges) == 1


# ── Query: get_project_ego_graph ───────────────────────────────────


class TestGetProjectEgoGraph:
    def test_returns_agraph_format(self):
        session = _make_session()
        project = _make_project(session, name="ego-project", tags=["Agent"], topics=["llm"])
        build_project_graph(session, project)

        result = get_project_ego_graph(session, project.id)

        assert "nodes" in result
        assert "edges" in result
        # Project + 1 Domain + 1 Capability = 3 nodes
        assert len(result["nodes"]) == 3
        # belongs_to + provides = 2 edges
        assert len(result["edges"]) == 2

        # Check node format
        for node in result["nodes"]:
            assert "id" in node
            assert "label" in node
            assert "node_type" in node
            assert "size" in node

        # Project node should be bigger
        project_node = [n for n in result["nodes"] if n["node_type"] == "Project"][0]
        assert project_node["size"] == 25
        other_node = [n for n in result["nodes"] if n["node_type"] != "Project"][0]
        assert other_node["size"] == 15

        # Check edge format
        for edge in result["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "label" in edge
            assert "relation_type" in edge

    def test_empty_graph_for_unknown_project(self):
        session = _make_session()
        result = get_project_ego_graph(session, 9999)
        assert result["nodes"] == []
        assert result["edges"] == []


# ── Query: find_projects_by_* ──────────────────────────────────────


class TestFindProjects:
    def test_find_by_dependency(self):
        session = _make_session()
        p = _make_project(session, name="dep-user")
        build_project_graph(session, p)
        add_dependency(session, p, "pytorch")

        results = find_projects_by_dependency(session, "pytorch")
        assert len(results) == 1
        assert results[0].name == "dep-user"

    def test_find_by_capability(self):
        session = _make_session()
        p = _make_project(session, name="cap-provider", topics=["embedding"])
        build_project_graph(session, p)

        results = find_projects_by_capability(session, "embedding")
        assert len(results) == 1
        assert results[0].name == "cap-provider"

    def test_find_by_domain(self):
        session = _make_session()
        p = _make_project(session, name="agent-proj", tags=["Agent"])
        build_project_graph(session, p)

        results = find_projects_by_domain(session, "Agent")
        assert len(results) == 1
        assert results[0].name == "agent-proj"

    def test_find_returns_empty_for_nonexistent(self):
        session = _make_session()
        assert find_projects_by_dependency(session, "nonexistent") == []
        assert find_projects_by_capability(session, "nonexistent") == []
        assert find_projects_by_domain(session, "nonexistent") == []

    def test_multiple_projects_same_domain(self):
        session = _make_session()
        p1 = _make_project(session, name="a1", repo_full_name="t/a1", tags=["Agent"])
        p2 = _make_project(session, name="a2", repo_full_name="t/a2", tags=["Agent"])
        build_project_graph(session, p1)
        build_project_graph(session, p2)

        results = find_projects_by_domain(session, "Agent")
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"a1", "a2"}
