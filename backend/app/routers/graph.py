"""Graph router: knowledge graph data for vis-network visualization."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.repositories import ProjectRepository

router = APIRouter()


class GraphNodeOut(BaseModel):
    id: str
    label: str
    group: str
    title: str
    color: str
    size: int
    shape: str


class GraphEdgeOut(BaseModel):
    from_: str
    to: str
    label: str
    color: str = "#cccccc"


class TopicGraphResponse(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    stats: dict
    topic_distribution: dict[str, int]


PROJECT_COLOR = "#4e79a7"
TOPIC_COLOR = "#f28e2b"


@router.get("/topic-graph", response_model=TopicGraphResponse)
async def get_topic_graph(session: Session = Depends(get_session)):
    repo = ProjectRepository(session)
    projects = repo.list_with_options()

    nodes: list[GraphNodeOut] = []
    edges: list[GraphEdgeOut] = []
    topic_nodes: dict[str, GraphNodeOut] = {}
    project_count = 0

    # Topic distribution
    topic_counts: dict[str, int] = {}

    for p in projects:
        if not p.id:
            continue
        project_count += 1

        project_node = GraphNodeOut(
            id=f"project_{p.id}",
            label=p.name,
            group="project",
            title=f"Project: {p.name}\nStars: {p.stars}\nLanguage: {p.language or '-'}",
            color=PROJECT_COLOR,
            size=25,
            shape="dot",
        )
        nodes.append(project_node)

        for topic in p.topics or []:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

            if topic not in topic_nodes:
                topic_node = GraphNodeOut(
                    id=f"topic_{topic}",
                    label=topic,
                    group="topic",
                    title=f"Topic: {topic}",
                    color=TOPIC_COLOR,
                    size=15,
                    shape="diamond",
                )
                topic_nodes[topic] = topic_node
                nodes.append(topic_node)

            edges.append(
                GraphEdgeOut(
                    from_=f"project_{p.id}",
                    to=f"topic_{topic}",
                    label=f"{p.name} -> {topic}",
                )
            )

    return TopicGraphResponse(
        nodes=nodes,
        edges=edges,
        stats={
            "project_count": project_count,
            "topic_count": len(topic_nodes),
            "edge_count": len(edges),
        },
        topic_distribution=dict(sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:30]),
    )
