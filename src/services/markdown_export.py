"""Markdown export service for projects, trials, and shares.

Generates structured Markdown documents suitable for Obsidian / Confluence,
including project metadata, evaluation scores, trial records, and graph
relationships.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session

from src.models import Project, Share, Trial
from src.repositories import (
    EvaluationRepository,
    GraphRepository,
    ProjectRepository,
)


def _fmt_date(dt: datetime | None) -> str:
    """Format a datetime to YYYY-MM-DD, or return '-' if None."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d")


def _fmt_score(score: int | None) -> str:
    """Format a score value, or return '-' if None."""
    if score is None:
        return "-"
    return str(score)


def _safe_text(text: str | None) -> str:
    """Return text or 'N/A' if None/empty."""
    if not text:
        return "N/A"
    return text


def _build_graph_relations_section(
    session: Session,
    project_id: int,
) -> str:
    """Build a Markdown section listing graph relationships for a project."""
    graph_repo = GraphRepository(session)
    nodes, edges = graph_repo.get_one_hop(project_id)

    if not edges:
        return ""

    # Build a lookup for node names
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


def export_evaluation_markdown(session: Session, project_id: int) -> str:
    """Generate Markdown for a project evaluation card.

    Includes project metadata, evaluation scores, decision, and graph
    relationships.
    """
    project_repo = ProjectRepository(session)
    project = project_repo.get(project_id)
    if project is None:
        return ""

    eval_repo = EvaluationRepository(session)
    evaluations = eval_repo.list_by_project(project_id)

    lines: list[str] = [
        f"# {project.name}",
        "",
        f"> {project.github_url}",
        "",
    ]

    # Project metadata
    lines.append("## 项目信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 名称 | {project.name} |")
    lines.append(f"| 仓库 | {project.repo_full_name} |")
    lines.append(f"| 描述 | {_safe_text(project.description)} |")
    lines.append(f"| Stars | {project.stars} |")
    lines.append(f"| Forks | {project.forks} |")
    lines.append(f"| 语言 | {_safe_text(project.language)} |")
    lines.append(f"| 许可证 | {_safe_text(project.license)} |")
    lines.append(f"| 标签 | {', '.join(project.tags) if project.tags else '-'} |")
    lines.append(f"| Topics | {', '.join(project.topics) if project.topics else '-'} |")
    lines.append(f"| 池 | {project.pool} |")
    lines.append(f"| 来源 | {project.source} |")
    lines.append(f"| 首次发现 | {_fmt_date(project.first_seen_at)} |")
    lines.append(f"| 最近推送 | {_fmt_date(project.last_pushed_at)} |")
    lines.append(f"| 过滤状态 | {project.filter_status} |")
    if project.filter_reason:
        lines.append(f"| 过滤原因 | {project.filter_reason} |")
    lines.append("")

    # README summary
    if project.readme_summary:
        lines.append("## README 摘要")
        lines.append("")
        lines.append(project.readme_summary)
        lines.append("")

    # Evaluations
    if evaluations:
        lines.append("## 评估记录")
        lines.append("")
        for i, ev in enumerate(evaluations, 1):
            lines.append(f"### 评估 #{i}")
            lines.append("")
            lines.append(f"- **推荐分**: {_fmt_score(ev.recommendation_score)}")
            lines.append(f"- **相关分**: {_fmt_score(ev.relevance_score)}")
            lines.append(f"- **可试分**: {_fmt_score(ev.trialability_score)}")
            lines.append(f"- **价值分**: {_fmt_score(ev.value_score)}")
            lines.append(f"- **决策**: {ev.decision}")
            if ev.decision_reason:
                lines.append(f"- **决策原因**: {ev.decision_reason}")
            if ev.evidence:
                lines.append(f"- **证据**: {ev.evidence}")
            if ev.evaluated_by:
                lines.append(f"- **评估人**: {ev.evaluated_by}")
            lines.append(f"- **评估时间**: {_fmt_date(ev.evaluated_at)}")
            lines.append("")

    # Graph relationships
    graph_section = _build_graph_relations_section(session, project_id)
    if graph_section:
        lines.append(graph_section)

    return "\n".join(lines)


def export_trial_markdown(session: Session, trial_id: int) -> str:
    """Generate Markdown for a trial record.

    Includes project info, trial status, owner, environment, and results.
    """
    trial = session.get(Trial, trial_id)
    if trial is None:
        return ""

    project_repo = ProjectRepository(session)
    project = project_repo.get(trial.project_id)

    project_name = project.name if project else f"Project#{trial.project_id}"
    project_url = project.github_url if project else ""

    lines: list[str] = [
        f"# 试用记录: {project_name}",
        "",
    ]

    if project_url:
        lines.append(f"> 项目地址: {project_url}")
        lines.append("")

    lines.append("## 试用信息")
    lines.append("")
    lines.append("| 字段 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 负责人 | {trial.owner} |")
    lines.append(f"| 状态 | {trial.status} |")
    lines.append(f"| 认领时间 | {_fmt_date(trial.claimed_at)} |")
    lines.append(f"| 截止日期 | {_fmt_date(trial.due_date) if trial.due_date else '-'} |")
    if trial.environment:
        lines.append(f"| 环境 | {trial.environment} |")
    if trial.demo_url:
        lines.append(f"| Demo URL | {trial.demo_url} |")
    if trial.next_action:
        lines.append(f"| 下一步 | {trial.next_action} |")
    lines.append("")

    if trial.trial_notes:
        lines.append("## 试用笔记")
        lines.append("")
        lines.append(trial.trial_notes)
        lines.append("")

    if trial.result_summary:
        lines.append("## 结论")
        lines.append("")
        lines.append(trial.result_summary)
        lines.append("")

    if trial.blockers:
        lines.append("## 阻碍")
        lines.append("")
        lines.append(trial.blockers)
        lines.append("")

    # Graph relationships for the project
    if project is not None:
        graph_section = _build_graph_relations_section(session, project.id)
        if graph_section:
            lines.append(graph_section)

    return "\n".join(lines)


def export_share_markdown(session: Session, share_id: int) -> str:
    """Generate Markdown for a share / knowledge archive record.

    Includes share metadata, key findings, reusable patterns, applicable
    scenarios, and graph relationships.
    """
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

    # Graph relationships
    if project is not None:
        graph_section = _build_graph_relations_section(session, project.id)
        if graph_section:
            lines.append(graph_section)

    return "\n".join(lines)
