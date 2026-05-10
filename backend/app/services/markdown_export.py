"""Markdown export service for projects, trials, and shares."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from app.models import Project, Share, Trial
from app.repositories import (
    EvaluationRepository,
    GraphRepository,
    ProjectRepository,
)


def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d")


def _fmt_score(score: int | None) -> str:
    if score is None:
        return "-"
    return str(score)


def _safe_text(text: str | None) -> str:
    if not text:
        return "N/A"
    return text


def _build_graph_relations_section(
    session: Session,
    project_id: int,
) -> str:
    graph_repo = GraphRepository(session)
    nodes, edges = graph_repo.get_one_hop(project_id)

    if not edges:
        return ""

    node_map = {n.id: n for n in nodes}

    sections: dict[str, list[str]] = {
        "belongs_to": [],
        "provides": [],
        "depends_on": [],
        "similar_to": [],
        "produced": [],
    }

    for edge in edges:
        rt = edge.relation_type
        if rt not in sections:
            continue

        source_node = node_map.get(edge.source_node_id)
        target_node = node_map.get(edge.target_node_id)
        if source_node is None or target_node is None:
            continue

        source_label = source_node.name
        target_label = target_node.name
        sections[rt].append(f"- {source_label} → {target_label}")

    lines: list[str] = []
    for rt, entries in sections.items():
        if entries:
            lines.append(f"**{rt}**")
            lines.extend(entries)
            lines.append("")

    if not lines:
        return ""

    return "## 图谱关系\n\n" + "\n".join(lines)


def export_share_markdown(session: Session, share_id: int) -> str:
    """Generate Markdown for a share / knowledge archive record."""
    share = session.get(Share, share_id)
    if share is None:
        return ""

    trial = session.get(Trial, share.trial_id)
    project: Project | None = None
    if trial is not None:
        project_repo = ProjectRepository(session)
        project = project_repo.get(trial.project_id)

    project_name = project.name if project else "Unknown Project"

    lines: list[str] = [
        f"# 分享归档: {share.title}",
        "",
        f"> 项目: {project_name}",
        "",
    ]

    lines.append("## 基本信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 标题 | {share.title} |")
    if share.shared_by:
        lines.append(f"| 分享人 | {share.shared_by} |")
    lines.append(f"| 分享时间 | {_fmt_date(share.shared_at)} |")
    if share.knowledge_doc_url:
        lines.append(f"| 文档链接 | {share.knowledge_doc_url} |")
    lines.append("")

    if share.summary:
        lines.append("## 摘要")
        lines.append("")
        lines.append(share.summary)
        lines.append("")

    if share.key_findings:
        lines.append("## 核心发现")
        lines.append("")
        lines.append(share.key_findings)
        lines.append("")

    if share.reusable_patterns:
        lines.append("## 可复用模式")
        lines.append("")
        lines.append(share.reusable_patterns)
        lines.append("")

    if share.applicable_scenarios:
        lines.append("## 适用场景")
        lines.append("")
        lines.append(share.applicable_scenarios)
        lines.append("")

    if project is not None:
        graph_section = _build_graph_relations_section(session, project.id)
        if graph_section:
            lines.append(graph_section)

    return "\n".join(lines)
