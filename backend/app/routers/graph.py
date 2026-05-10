"""Graph router: knowledge graph data for vis-network visualization."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.repositories import ProjectRepository

router = APIRouter()


class TopicGraphResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    stats: dict
    topic_distribution: dict[str, int]


PROJECT_COLOR = "#4e79a7"
DIRECTION_COLOR = "#59a14f"


@router.get("/topic-graph", response_model=TopicGraphResponse)
async def get_topic_graph(session: Session = Depends(get_session)):
    repo = ProjectRepository(session)
    projects = repo.list_with_options()

    nodes: list[dict] = []
    edges: list[dict] = []
    direction_nodes: dict[str, dict] = {}
    project_count = 0
    direction_counts: dict[str, int] = {}

    for p in projects:
        if not p.id:
            continue
        project_count += 1

        nodes.append({
            "id": f"project_{p.id}",
            "label": p.name,
            "group": "project",
            "title": f"Project: {p.name}\nStars: {p.stars}\nLanguage: {p.language or '-'}",
            "color": PROJECT_COLOR,
            "size": 25,
            "shape": "dot",
        })

        for tag in p.tags or []:
            direction_counts[tag] = direction_counts.get(tag, 0) + 1

            if tag not in direction_nodes:
                direction_node = {
                    "id": f"direction_{tag}",
                    "label": tag,
                    "group": "direction",
                    "title": f"Direction: {tag}",
                    "color": DIRECTION_COLOR,
                    "size": 30,
                    "shape": "diamond",
                }
                direction_nodes[tag] = direction_node
                nodes.append(direction_node)

            edges.append({
                "from": f"project_{p.id}",
                "to": f"direction_{tag}",
                "label": f"{p.name} -> {tag}",
                "color": "#cccccc",
            })

    return TopicGraphResponse(
        nodes=nodes,
        edges=edges,
        stats={
            "project_count": project_count,
            "topic_count": len(direction_nodes),
            "edge_count": len(edges),
        },
        topic_distribution=dict(sorted(direction_counts.items(), key=lambda x: x[1], reverse=True)),
    )
