"""Graph builder: creates and queries project knowledge graph.

Builds GraphNode/GraphEdge entries from Project tags, topics, and Share
records.  Provides query interfaces that return data formatted for
streamlit-agraph visualisation.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from src.models import GraphEdge, GraphNode, Project, Share
from src.repositories import GraphRepository, ProjectRepository


# ── Node / Edge helpers ────────────────────────────────────────────


def _ensure_node(
    repo: GraphRepository,
    *,
    node_type: str,
    name: str,
    ref_table: str | None = None,
    ref_id: int | None = None,
    description: str | None = None,
) -> GraphNode:
    """Return an existing node or create one if it doesn't exist."""
    from sqlmodel import select

    statement = select(GraphNode).where(
        GraphNode.node_type == node_type,
        GraphNode.name == name,
    )
    if ref_table is not None:
        statement = statement.where(GraphNode.ref_table == ref_table)
    if ref_id is not None:
        statement = statement.where(GraphNode.ref_id == ref_id)

    existing = repo.session.exec(statement).first()
    if existing is not None:
        return existing

    node = GraphNode(
        node_type=node_type,
        name=name,
        ref_table=ref_table,
        ref_id=ref_id,
        description=description,
    )
    return repo.create_node(node)


def _ensure_edge(
    repo: GraphRepository,
    *,
    source_node_id: int,
    target_node_id: int,
    relation_type: str,
    source: str = "auto",
    confidence: float = 1.0,
    evidence: str | None = None,
) -> GraphEdge:
    """Return an existing edge or create one if it doesn't exist."""
    from sqlmodel import select

    statement = select(GraphEdge).where(
        GraphEdge.source_node_id == source_node_id,
        GraphEdge.target_node_id == target_node_id,
        GraphEdge.relation_type == relation_type,
    )
    existing = repo.session.exec(statement).first()
    if existing is not None:
        return existing

    edge = GraphEdge(
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        relation_type=relation_type,
        source=source,
        confidence=confidence,
        evidence=evidence,
    )
    return repo.create_edge(edge)


# ── Build operations ───────────────────────────────────────────────


def build_project_graph(session: Session, project: Project) -> None:
    """Create graph nodes and edges for a project.

    - Creates a Project node linked to the project row.
    - For each tag, creates a Domain node and ``belongs_to`` edge.
    - For each topic, creates a Capability node and ``provides`` edge.
    """
    graph_repo = GraphRepository(session)

    # 1. Project node
    project_node = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project.name,
        ref_table="projects",
        ref_id=project.id,
        description=project.description,
    )

    # 2. Domain nodes from tags (Agent, RAG, Eval, …)
    for tag in project.tags or []:
        domain_node = _ensure_node(
            graph_repo,
            node_type="Domain",
            name=tag,
            description=f"Domain: {tag}",
        )
        _ensure_edge(
            graph_repo,
            source_node_id=project_node.id,
            target_node_id=domain_node.id,
            relation_type="belongs_to",
            source="auto",
            confidence=1.0,
            evidence=f"Tag: {tag}",
        )

    # 3. Capability nodes from topics
    for topic in project.topics or []:
        capability_node = _ensure_node(
            graph_repo,
            node_type="Capability",
            name=topic,
            description=f"Capability: {topic}",
        )
        _ensure_edge(
            graph_repo,
            source_node_id=project_node.id,
            target_node_id=capability_node.id,
            relation_type="provides",
            source="auto",
            confidence=1.0,
            evidence=f"Topic: {topic}",
        )


def add_dependency(
    session: Session,
    project: Project,
    dependency_name: str,
    *,
    created_by: str | None = None,
) -> None:
    """Create a Dependency node and ``depends_on`` edge for a project."""
    graph_repo = GraphRepository(session)

    project_node = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project.name,
        ref_table="projects",
        ref_id=project.id,
        description=project.description,
    )
    dep_node = _ensure_node(
        graph_repo,
        node_type="Dependency",
        name=dependency_name,
        description=f"Dependency: {dependency_name}",
    )
    edge = GraphEdge(
        source_node_id=project_node.id,
        target_node_id=dep_node.id,
        relation_type="depends_on",
        source="manual",
        confidence=1.0,
        created_by=created_by,
    )
    graph_repo.create_edge(edge)


def add_similar_to(
    session: Session,
    project_a: Project,
    project_b: Project,
    *,
    created_by: str | None = None,
    evidence: str | None = None,
) -> None:
    """Create a bidirectional ``similar_to`` edge between two projects."""
    graph_repo = GraphRepository(session)

    node_a = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project_a.name,
        ref_table="projects",
        ref_id=project_a.id,
        description=project_a.description,
    )
    node_b = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project_b.name,
        ref_table="projects",
        ref_id=project_b.id,
        description=project_b.description,
    )
    edge = GraphEdge(
        source_node_id=node_a.id,
        target_node_id=node_b.id,
        relation_type="similar_to",
        source="manual",
        confidence=1.0,
        evidence=evidence,
        created_by=created_by,
    )
    graph_repo.create_edge(edge)


def build_share_graph(session: Session, share: Share) -> None:
    """Create TeamAsset node and ``produced`` edge for a share record."""
    graph_repo = GraphRepository(session)

    from src.models import Trial

    trial = session.get(Trial, share.trial_id)
    if trial is None:
        return

    project_repo = ProjectRepository(session)
    project = project_repo.get(trial.project_id)
    if project is None:
        return

    project_node = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project.name,
        ref_table="projects",
        ref_id=project.id,
        description=project.description,
    )
    team_asset_node = _ensure_node(
        graph_repo,
        node_type="TeamAsset",
        name=share.title,
        ref_table="shares",
        ref_id=share.id,
        description=share.summary,
    )
    _ensure_edge(
        graph_repo,
        source_node_id=project_node.id,
        target_node_id=team_asset_node.id,
        relation_type="produced",
        source="auto",
        confidence=1.0,
        evidence=share.title,
    )


# ── Query operations ───────────────────────────────────────────────


def get_project_ego_graph(
    session: Session,
    project_id: int,
) -> dict[str, list[dict[str, Any]]]:
    """Return the one-hop ego graph for a project, formatted for streamlit-agraph.

    Returns::

        {
            "nodes": [{"id": ..., "label": ..., "node_type": ..., "size": ...}],
            "edges": [{"source": ..., "target": ..., "label": ..., "relation_type": ...}],
        }
    """
    graph_repo = GraphRepository(session)
    nodes, edges = graph_repo.get_one_hop(project_id)

    agraph_nodes: list[dict[str, Any]] = []
    for node in nodes:
        size = 25 if node.node_type == "Project" else 15
        agraph_nodes.append(
            {
                "id": node.id,
                "label": node.name,
                "node_type": node.node_type,
                "size": size,
            }
        )

    agraph_edges: list[dict[str, Any]] = []
    for edge in edges:
        agraph_edges.append(
            {
                "source": edge.source_node_id,
                "target": edge.target_node_id,
                "label": edge.relation_type,
                "relation_type": edge.relation_type,
            }
        )

    return {"nodes": agraph_nodes, "edges": agraph_edges}


def find_projects_by_dependency(session: Session, name: str) -> list[Project]:
    """Find all projects that depend on the given dependency."""
    graph_repo = GraphRepository(session)
    return list(graph_repo.find_projects_by_related_node("Dependency", name))


def find_projects_by_capability(session: Session, name: str) -> list[Project]:
    """Find all projects that provide the given capability."""
    graph_repo = GraphRepository(session)
    return list(graph_repo.find_projects_by_related_node("Capability", name))


def find_projects_by_domain(session: Session, name: str) -> list[Project]:
    """Find all projects that belong to the given domain."""
    graph_repo = GraphRepository(session)
    return list(graph_repo.find_projects_by_related_node("Domain", name))
