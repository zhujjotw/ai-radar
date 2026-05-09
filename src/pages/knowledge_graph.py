"""Knowledge graph page: topic-based graph visualization from project topics."""

from __future__ import annotations

import streamlit as st
from streamlit_agraph import agraph
from streamlit_agraph import Config as AgraphConfig
from streamlit_agraph import Edge as AgraphEdge
from streamlit_agraph import Node as AgraphNode

from src.db import get_session, init_db
from src.repositories import ProjectRepository

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)

# --- Page header ---
st.title("Knowledge Graph")
st.caption("基于 GitHub Topics 的项目知识图谱")

# --- Load all projects ---
all_projects = _project_repo.list_with_options()

if not all_projects:
    st.info("没有找到项目。请先导入项目。")
else:
    # --- Build graph data from project topics ---
    nodes: list[AgraphNode] = []
    edges: list[AgraphEdge] = []

    # Track unique topics and projects
    topic_nodes: dict[str, AgraphNode] = {}
    project_nodes: dict[int, AgraphNode] = {}

    # Colors for different node types
    PROJECT_COLOR = "#4e79a7"  # Blue
    TOPIC_COLOR = "#f28e2b"  # Orange

    # Build nodes and edges
    for project in all_projects:
        if not project.id:
            continue

        # Create project node
        project_node = AgraphNode(
            id=f"project_{project.id}",
            label=project.name,
            title=f"Project: {project.name}\nStars: {project.stars}\nLanguage: {project.language or '-'}",
            color=PROJECT_COLOR,
            size=25,
            shape="dot",
        )
        project_nodes[project.id] = project_node
        nodes.append(project_node)

        # Create topic nodes and edges
        topics = project.topics or []
        for topic in topics:
            # Create topic node if not exists
            if topic not in topic_nodes:
                topic_node = AgraphNode(
                    id=f"topic_{topic}",
                    label=topic,
                    title=f"Topic: {topic}",
                    color=TOPIC_COLOR,
                    size=15,
                    shape="diamond",
                )
                topic_nodes[topic] = topic_node
                nodes.append(topic_node)

            # Create edge from project to topic
            edge = AgraphEdge(
                source=f"project_{project.id}",
                target=f"topic_{topic}",
                color="#cccccc",
                title=f"{project.name} → {topic}",
            )
            edges.append(edge)

    # --- Display graph ---
    st.subheader(f"项目-Topic 图谱 (共 {len(project_nodes)} 个项目, {len(topic_nodes)} 个 Topic)")

    # Graph configuration
    config = AgraphConfig(
        width=1400,
        height=800,
        directed=True,
        physics=True,
        hierarchical=False,
        stabilization=True,
        solver="forceAtlas2Based",
    )

    # Render graph
    agraph(nodes=nodes, edges=edges, config=config)

    # --- Statistics ---
    st.divider()
    st.subheader("统计信息")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("项目数量", len(project_nodes))
    with col2:
        st.metric("Topic 数量", len(topic_nodes))
    with col3:
        st.metric("连接数量", len(edges))

    # --- Topic distribution ---
    st.divider()
    st.subheader("Topic 分布")

    # Count projects per topic
    topic_counts: dict[str, int] = {}
    for project in all_projects:
        for topic in project.topics or []:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    # Sort by count
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

    # Display as bar chart
    if sorted_topics:
        chart_data = {
            "Topic": [t[0] for t in sorted_topics[:20]],  # Top 20
            "项目数量": [t[1] for t in sorted_topics[:20]],
        }
        st.bar_chart(chart_data, x="Topic", y="项目数量")
    else:
        st.info("没有找到 Topic 数据。")

    # --- Project list with topics ---
    st.divider()
    st.subheader("项目详情")

    # Filter by topic
    all_topics = sorted(topic_counts.keys())
    selected_topic = st.selectbox(
        "按 Topic 筛选",
        options=["所有 Topic"] + all_topics,
        key="kg_topic_filter",
    )

    # Filter projects
    if selected_topic == "所有 Topic":
        filtered_projects = all_projects
    else:
        filtered_projects = [p for p in all_projects if selected_topic in (p.topics or [])]

    # Display projects
    for project in filtered_projects:
        with st.expander(f"**{project.name}** — ⭐{project.stars}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Stars:** {project.stars:,}")
                st.markdown(f"**Forks:** {project.forks:,}")
                st.markdown(f"**Language:** {project.language or '-'}")
            with col2:
                st.markdown(f"**Pool:** {project.pool}")
                st.markdown(f"**Source:** {project.source}")
                if project.last_pushed_at:
                    st.markdown(f"**Last Push:** {project.last_pushed_at.strftime('%Y-%m-%d')}")
            with col3:
                st.markdown(f"[GitHub]({project.github_url})")
                if project.tags:
                    st.markdown("**Tags:** " + " · ".join(project.tags))

            if project.description:
                st.markdown(f"> {project.description}")

            if project.topics:
                st.markdown("**Topics:** " + " · ".join(project.topics))

            if project.llm_description:
                st.divider()
                st.markdown(f"**项目描述:** {project.llm_description}")
                if project.llm_scenarios:
                    st.markdown(f"**适用场景:**\n{project.llm_scenarios}")
