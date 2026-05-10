"""Graph builder: creates and queries project knowledge graph."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.models import GraphEdge, GraphNode, Project, Share
from app.repositories import GraphRepository, ProjectRepository


def _ensure_node(
    repo: GraphRepository,
    *,
    node_type: str,
    name: str,
    ref_table: str | None = None,
    ref_id: int | None = None,
    description: str | None = None,
) -> GraphNode:
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


def build_project_graph(session: Session, project: Project) -> None:
    graph_repo = GraphRepository(session)

    project_node = _ensure_node(
        graph_repo,
        node_type="Project",
        name=project.name,
        ref_table="projects",
        ref_id=project.id,
        description=project.description,
    )

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


def build_share_graph(session: Session, share: Share) -> None:
    graph_repo = GraphRepository(session)

    from app.models import Trial

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


def get_project_ego_graph(
    session: Session,
    project_id: int,
) -> dict[str, list[dict[str, Any]]]:
    graph_repo = GraphRepository(session)
    nodes, edges = graph_repo.get_one_hop(project_id)

    result_nodes: list[dict[str, Any]] = []
    for node in nodes:
        size = 25 if node.node_type == "Project" else 15
        result_nodes.append(
            {
                "id": node.id,
                "label": node.name,
                "node_type": node.node_type,
                "size": size,
            }
        )

    result_edges: list[dict[str, Any]] = []
    for edge in edges:
        result_edges.append(
            {
                "source": edge.source_node_id,
                "target": edge.target_node_id,
                "label": edge.relation_type,
                "relation_type": edge.relation_type,
            }
        )

    return {"nodes": result_nodes, "edges": result_edges}
