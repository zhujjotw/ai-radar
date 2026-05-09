"""Knowledge graph page: one-hop ego graph visualization and reverse lookup."""

from __future__ import annotations

import streamlit as st
from streamlit_agraph import agraph
from streamlit_agraph import Config as AgraphConfig
from streamlit_agraph import Edge as AgraphEdge
from streamlit_agraph import Node as AgraphNode

from src.db import get_session, init_db
from src.repositories import GraphRepository, ProjectRepository
from src.services.graph_builder import (
    find_projects_by_capability,
    find_projects_by_dependency,
    find_projects_by_domain,
    get_project_ego_graph,
)

# Node type color mapping for visual distinction
_NODE_COLORS: dict[str, str] = {
    "Project": "#4e79a7",
    "Domain": "#f28e2b",
    "Capability": "#59a14f",
    "Dependency": "#e15759",
    "TeamAsset": "#b07aa1",
}

# Relation type display labels
_RELATION_LABELS: dict[str, str] = {
    "belongs_to": "belongs to",
    "provides": "provides",
    "depends_on": "depends on",
    "similar_to": "similar to",
    "produced": "produced",
}

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)
_graph_repo = GraphRepository(_session)

# --- Page header ---
st.title("Knowledge Graph")
st.caption("Visualize project relationships and perform reverse lookups")

# --- Tab layout ---
tab_ego, tab_reverse = st.tabs(["Project Ego Graph", "Reverse Lookup"])

# =========================================================================
# Tab 1: Project Ego Graph — one-hop relationship visualization
# =========================================================================
with tab_ego:
    # Project selector
    all_projects = _project_repo.list_with_options(order_by="name", order_desc=False)

    if not all_projects:
        st.info("No projects found. Import projects first.")
    else:
        project_options = {f"{p.name} ({p.repo_full_name})": p for p in all_projects}
        selected_label = st.selectbox(
            "Select a project",
            options=list(project_options.keys()),
            key="kg_project_select",
        )
        selected_project = project_options[selected_label]

        # Fetch ego graph data
        ego_data = get_project_ego_graph(_session, selected_project.id)

        if not ego_data["nodes"]:
            st.warning(
                f"No graph relationships found for **{selected_project.name}**. "
                "Run graph building or add relationships first."
            )
        else:
            # Build agraph Node/Edge objects
            agraph_nodes: list[AgraphNode] = []
            for node in ego_data["nodes"]:
                node_type = node["node_type"]
                agraph_nodes.append(
                    AgraphNode(
                        id=str(node["id"]),
                        label=node["label"],
                        title=f"{node_type}: {node['label']}",
                        color=_NODE_COLORS.get(node_type, "#999999"),
                        size=node["size"],
                    )
                )

            agraph_edges: list[AgraphEdge] = []
            for edge in ego_data["edges"]:
                agraph_edges.append(
                    AgraphEdge(
                        source=str(edge["source"]),
                        target=str(edge["target"]),
                        color="#cccccc",
                    )
                )

            config = AgraphConfig(
                width=800,
                height=500,
                directed=True,
                physics=True,
                hierarchical=False,
            )

            agraph(nodes=agraph_nodes, edges=agraph_edges, config=config)

            # Relationship list below the graph
            st.divider()
            st.subheader("Relationships")

            # Build a lookup for node names by id
            node_lookup = {str(n["id"]): n["label"] for n in ego_data["nodes"]}

            # Group edges by relation type
            for rel_type, rel_label in _RELATION_LABELS.items():
                matching_edges = [e for e in ego_data["edges"] if e["relation_type"] == rel_type]
                if not matching_edges:
                    continue

                st.markdown(f"**{rel_label}** ({len(matching_edges)})")
                for edge in matching_edges:
                    source_name = node_lookup.get(str(edge["source"]), "?")
                    target_name = node_lookup.get(str(edge["target"]), "?")
                    st.markdown(f"- {source_name} → {target_name}")

# =========================================================================
# Tab 2: Reverse Lookup — find projects by capability/dependency/domain
# =========================================================================
with tab_reverse:
    st.subheader("Find Projects by Relationship")

    lookup_type = st.selectbox(
        "Lookup type",
        options=["Capability", "Dependency", "Domain"],
        key="kg_lookup_type",
    )

    # Get available node names for the selected type
    available_names = _graph_repo.list_node_names_by_type(lookup_type)

    if not available_names:
        st.info(f"No {lookup_type} nodes found in the knowledge graph.")
    else:
        selected_name = st.selectbox(
            f"Select a {lookup_type}",
            options=available_names,
            key="kg_lookup_name",
        )

        # Find related projects
        if lookup_type == "Capability":
            projects = find_projects_by_capability(_session, selected_name)
        elif lookup_type == "Dependency":
            projects = find_projects_by_dependency(_session, selected_name)
        else:
            projects = find_projects_by_domain(_session, selected_name)

        st.divider()

        if not projects:
            st.info(f"No projects found for {lookup_type}: **{selected_name}**")
        else:
            st.caption(f"Found {len(projects)} project(s)")

            for project in projects:
                with st.expander(f"**{project.name}** — {project.repo_full_name}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Stars:** {project.stars}")
                        st.markdown(f"**Language:** {project.language or '-'}")
                    with col2:
                        st.markdown(f"**Pool:** {project.pool}")
                        st.markdown(f"**Source:** {project.source}")
                    with col3:
                        st.markdown(f"[GitHub]({project.github_url})")
                        if project.tags:
                            st.markdown("**Tags:** " + ", ".join(project.tags))

                    if project.description:
                        st.markdown(f"> {project.description}")
