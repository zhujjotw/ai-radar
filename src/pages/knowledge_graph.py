"""Knowledge graph page: topic-based graph visualization from project topics."""

from __future__ import annotations

import streamlit as st
from streamlit_agraph import agraph
from streamlit_agraph import Config as AgraphConfig
from streamlit_agraph import Edge as AgraphEdge
from streamlit_agraph import Node as AgraphNode

from src.db import get_session, init_db
from src.repositories import ProjectRepository


@st.cache_data(ttl=300)  # Cache for 5 minutes
def _load_projects():
    """Load projects from database with caching."""
    init_db()
    session = get_session()
    repo = ProjectRepository(session)
    projects = repo.list_with_options()
    # Convert to dict to make it hashable for caching
    return [
        {
            "id": p.id,
            "name": p.name,
            "github_url": p.github_url,
            "stars": p.stars,
            "forks": p.forks,
            "language": p.language,
            "pool": p.pool,
            "source": p.source,
            "last_pushed_at": p.last_pushed_at.strftime("%Y-%m-%d") if p.last_pushed_at else None,
            "description": p.description,
            "tags": p.tags or [],
            "topics": p.topics or [],
            "llm_description": p.llm_description,
            "llm_scenarios": p.llm_scenarios,
        }
        for p in projects
    ]


def _build_graph(projects_data):
    """Build graph nodes and edges from project data."""
    nodes: list[AgraphNode] = []
    edges: list[AgraphEdge] = []

    topic_nodes: dict[str, AgraphNode] = {}
    project_nodes: dict[int, AgraphNode] = {}

    PROJECT_COLOR = "#4e79a7"
    TOPIC_COLOR = "#f28e2b"

    for p in projects_data:
        project_id = p["id"]
        if not project_id:
            continue

        project_node = AgraphNode(
            id=f"project_{project_id}",
            label=p["name"],
            title=f"Project: {p['name']}\nStars: {p['stars']}\nLanguage: {p['language'] or '-'}",
            color=PROJECT_COLOR,
            size=25,
            shape="dot",
        )
        project_nodes[project_id] = project_node
        nodes.append(project_node)

        for topic in p["topics"]:
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

            edge = AgraphEdge(
                source=f"project_{project_id}",
                target=f"topic_{topic}",
                color="#cccccc",
                title=f"{p['name']} → {topic}",
            )
            edges.append(edge)

    return nodes, edges, project_nodes, topic_nodes


# --- Page header ---
st.title("Knowledge Graph")
st.caption("基于 GitHub Topics 的项目知识图谱")

# --- Load all projects (cached) ---
all_projects = _load_projects()

if not all_projects:
    st.info("没有找到项目。请先导入项目。")
else:
    # --- Build graph data ---
    nodes, edges, project_nodes, topic_nodes = _build_graph(all_projects)

    # --- Display graph ---
    st.subheader(f"项目-Topic 图谱 (共 {len(project_nodes)} 个项目, {len(topic_nodes)} 个 Topic)")

    config = AgraphConfig(
        width=1400,
        height=800,
        directed=True,
        physics=True,
        hierarchical=False,
        stabilization=True,
        solver="forceAtlas2Based",
    )

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

    topic_counts: dict[str, int] = {}
    for p in all_projects:
        for topic in p["topics"]:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

    if sorted_topics:
        chart_data = {
            "Topic": [t[0] for t in sorted_topics[:20]],
            "项目数量": [t[1] for t in sorted_topics[:20]],
        }
        st.bar_chart(chart_data, x="Topic", y="项目数量")
    else:
        st.info("没有找到 Topic 数据。")

    # --- Project list with topics ---
    st.divider()
    st.subheader("项目详情")

    all_topics = sorted(topic_counts.keys())
    selected_topic = st.selectbox(
        "按 Topic 筛选",
        options=["所有 Topic"] + all_topics,
        key="kg_topic_filter",
    )

    if selected_topic == "所有 Topic":
        filtered_projects = all_projects
    else:
        filtered_projects = [p for p in all_projects if selected_topic in p["topics"]]

    for p in filtered_projects:
        with st.expander(f"**{p['name']}** — ⭐{p['stars']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Stars:** {p['stars']:,}")
                st.markdown(f"**Forks:** {p['forks']:,}")
                st.markdown(f"**Language:** {p['language'] or '-'}")
            with col2:
                st.markdown(f"**Pool:** {p['pool']}")
                st.markdown(f"**Source:** {p['source']}")
                if p["last_pushed_at"]:
                    st.markdown(f"**Last Push:** {p['last_pushed_at']}")
            with col3:
                st.markdown(f"[GitHub]({p['github_url']})")
                if p["tags"]:
                    st.markdown("**Tags:** " + " · ".join(p["tags"]))

            if p["description"]:
                st.markdown(f"> {p['description']}")

            if p["topics"]:
                st.markdown("**Topics:** " + " · ".join(p["topics"]))

            if p["llm_description"]:
                st.divider()
                st.markdown(f"**项目描述:** {p['llm_description']}")
                if p["llm_scenarios"]:
                    st.markdown(f"**适用场景:**\n{p['llm_scenarios']}")
