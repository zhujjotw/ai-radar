"""Project Radar page: browse, filter, sort, and manage projects."""

from __future__ import annotations

import streamlit as st

from src.db import get_session, init_db
from src.models import Evaluation
from src.repositories import EvaluationRepository, ProjectRepository

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)
_evaluation_repo = EvaluationRepository(_session)

# --- Page header ---
st.title("Project Radar")
st.caption("Browse, filter, and evaluate AI open-source projects")

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")

    pool_filter = st.selectbox(
        "Pool",
        options=["All", "baseline", "candidate"],
        index=0,
    )

    filter_status_filter = st.selectbox(
        "Filter Status",
        options=["All", "needs_review", "passed", "filtered_out", "override"],
        index=0,
    )

    decision_filter = st.selectbox(
        "Decision",
        options=["All", "watch", "try", "reject"],
        index=0,
    )

    source_filter = st.selectbox(
        "Source",
        options=["All", "baseline", "github_search", "external", "manual"],
        index=0,
    )

    all_tags = _project_repo.get_all_tags()
    tag_filter = st.selectbox(
        "Tag",
        options=["All"] + all_tags,
        index=0,
    )

    st.divider()

    sort_options = {
        "Newest discovery": ("first_seen_at", True),
        "Recommendation score": ("recommendation_sort", True),
        "Recent update": ("last_pushed_at", True),
        "Unevaluated first": ("unevaluated_sort", True),
    }
    sort_label = st.selectbox("Sort by", options=list(sort_options.keys()), index=0)

st.divider()

# --- Fetch projects ---
kw: dict = {}
if pool_filter != "All":
    kw["pool"] = pool_filter
if filter_status_filter != "All":
    kw["filter_status"] = filter_status_filter
if decision_filter != "All":
    kw["decision"] = decision_filter
if source_filter != "All":
    kw["source"] = source_filter
if tag_filter != "All":
    kw["tag"] = tag_filter

order_key, order_desc = sort_options[sort_label]

if order_key in ("recommendation_sort", "unevaluated_sort"):
    # These need in-memory sorting with evaluation data
    projects = _project_repo.list_with_options(**{k: v for k, v in kw.items() if k != "order_by"})
else:
    projects = _project_repo.list_with_options(
        **{k: v for k, v in kw.items() if k != "order_by"},
        order_by=order_key,
        order_desc=order_desc,
    )

# --- In-memory sorting for special sort modes ---
if order_key == "recommendation_sort":
    _eval_cache: dict[int, Evaluation | None] = {}
    for p in projects:
        if p.id not in _eval_cache:
            _eval_cache[p.id] = _evaluation_repo.get_latest_by_project(p.id) if p.id else None
    projects.sort(
        key=lambda p: (
            _eval_cache.get(p.id) is not None,
            (getattr(_eval_cache.get(p.id), "recommendation_score", None) or 0),
        ),
        reverse=True,
    )
elif order_key == "unevaluated_sort":
    _eval_cache_unev: dict[int, Evaluation | None] = {}
    for p in projects:
        if p.id not in _eval_cache_unev:
            _eval_cache_unev[p.id] = _evaluation_repo.get_latest_by_project(p.id) if p.id else None
    projects.sort(
        key=lambda p: _eval_cache_unev.get(p.id) is None,
        reverse=True,
    )


# --- Display projects ---
if not projects:
    st.info("No projects match the current filters.")
else:
    st.caption(f"Showing {len(projects)} project(s)")

    for project in projects:
        evaluation = (
            _evaluation_repo.get_latest_by_project(project.id) if project.id else None
        )

        # Build header line
        decision_badge = f" [{evaluation.decision}]" if evaluation else ""
        filter_badge = f" [{project.filter_status}]" if project.filter_status != "needs_review" else ""
        header = f"**{project.name}** ⭐{project.stars}{decision_badge}{filter_badge}"

        with st.expander(header, expanded=False):
            # --- Project info ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"**Pool:** {project.pool}")
                st.markdown(f"**Source:** {project.source}")
            with col2:
                st.markdown(f"**Stars:** {project.stars}")
                st.markdown(f"**Forks:** {project.forks}")
            with col3:
                st.markdown(f"**Language:** {project.language or '-'}")
                st.markdown(f"**License:** {project.license or '-'}")

            if project.description:
                st.markdown(f"> {project.description}")

            if project.tags:
                st.markdown("**Tags:** " + ", ".join(project.tags))

            if project.topics:
                st.markdown("**Topics:** " + ", ".join(project.topics))

            st.markdown(
                f"[View on GitHub]({project.github_url})",
                unsafe_allow_html=False,
            )

            # --- Evaluation info ---
            if evaluation:
                st.divider()
                st.markdown("##### Current Evaluation")
                eval_cols = st.columns(4)
                eval_cols[0].metric("Relevance", evaluation.relevance_score or "-")
                eval_cols[1].metric("Trialability", evaluation.trialability_score or "-")
                eval_cols[2].metric("Value", evaluation.value_score or "-")
                eval_cols[3].metric("Recommendation", evaluation.recommendation_score or "-")
                if evaluation.evidence:
                    st.caption(evaluation.evidence)

            # --- Actions ---
            st.divider()

            action_col1, action_col2 = st.columns(2)

            with action_col1:
                st.markdown("##### Set Decision")
                new_decision = st.selectbox(
                    "Decision",
                    options=["watch", "try", "reject"],
                    index=["watch", "try", "reject"].index(evaluation.decision)
                    if evaluation and evaluation.decision in ("watch", "try", "reject")
                    else 0,
                    key=f"decision_{project.id}",
                )
                decision_reason = st.text_input(
                    "Reason (optional)",
                    value=evaluation.decision_reason or "" if evaluation else "",
                    key=f"reason_{project.id}",
                )
                if st.button("Save Decision", key=f"save_decision_{project.id}"):
                    if evaluation:
                        evaluation.decision = new_decision
                        evaluation.decision_reason = decision_reason or None
                        _evaluation_repo.update(evaluation)
                    else:
                        new_eval = Evaluation(
                            project_id=project.id,
                            decision=new_decision,
                            decision_reason=decision_reason or None,
                        )
                        _evaluation_repo.create(new_eval)
                    st.success(f"Decision set to **{new_decision}** for {project.name}")
                    st.rerun()

            with action_col2:
                st.markdown("##### Override Filter")
                if project.filter_status != "override":
                    override_reason = st.text_input(
                        "Override reason",
                        key=f"override_reason_{project.id}",
                    )
                    if st.button("Override Filter", key=f"override_{project.id}"):
                        if not override_reason:
                            st.warning("Please provide an override reason.")
                        else:
                            project.filter_status = "override"
                            project.filter_reason = override_reason
                            _project_repo.update(project)
                            st.success(f"Filter overridden for {project.name}")
                            st.rerun()
                else:
                    st.info(f"Already overridden: {project.filter_reason or 'No reason provided'}")
                    if st.button("Remove Override", key=f"remove_override_{project.id}"):
                        project.filter_status = "needs_review"
                        project.filter_reason = None
                        _project_repo.update(project)
                        st.success(f"Override removed for {project.name}")
                        st.rerun()
