"""Share archive page: create share records from completed trials, export Markdown."""

from __future__ import annotations

import streamlit as st

from src.db import get_session, init_db
from src.models import Share
from src.repositories import (
    ProjectRepository,
    ShareRepository,
    TrialRepository,
)
from src.services.graph_builder import build_share_graph
from src.services.markdown_export import export_share_markdown

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)
_trial_repo = TrialRepository(_session)
_share_repo = ShareRepository(_session)

# --- Page header ---
st.title("Shares")
st.caption("Create share archives from completed trials and export Markdown")

# --- Sidebar filters ---
with st.sidebar:
    st.header("Share Filters")

    shared_by_filter = st.text_input("Shared by", value="")

st.divider()

# --- Tab layout ---
tab_create, tab_list = st.tabs(["Create Share", "Share Archives"])

# =========================================================================
# Tab 1: Create Share from demo_done / shared trials
# =========================================================================
with tab_create:
    st.subheader("Trials Ready for Sharing (demo_done)")

    demo_done_trials = _trial_repo.list_by_status("demo_done")

    if not demo_done_trials:
        st.info(
            "No demo_done trials available. Complete a trial and mark it "
            "as demo_done in the Trials page first."
        )
    else:
        for trial in demo_done_trials:
            project = _project_repo.get(trial.project_id) if trial.project_id else None
            project_name = project.name if project else "Unknown Project"

            existing_share = _share_repo.get_by_trial_id(trial.id)
            if existing_share is not None:
                continue  # Already shared — skip

            header = f"**{project_name}** — {trial.owner} (result: {trial.result_summary or '-'})"

            with st.expander(header, expanded=False):
                # Project info
                if project:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Stars:** {project.stars}")
                        st.markdown(f"**Language:** {project.language or '-'}")
                    with col2:
                        st.markdown(f"[GitHub]({project.github_url})")
                        if project.tags:
                            st.markdown("**Tags:** " + ", ".join(project.tags))

                if trial.result_summary:
                    st.markdown(f"> {trial.result_summary}")

                # Share form
                st.divider()
                st.markdown("##### Create Share Record")

                share_title = st.text_input(
                    "Title",
                    value=f"{project_name} - Trial Report",
                    key=f"share_title_{trial.id}",
                )
                share_summary = st.text_area(
                    "Summary",
                    value=trial.result_summary or "",
                    key=f"share_summary_{trial.id}",
                )
                share_findings = st.text_area(
                    "Key Findings",
                    key=f"share_findings_{trial.id}",
                )
                share_patterns = st.text_area(
                    "Reusable Patterns",
                    key=f"share_patterns_{trial.id}",
                )
                share_scenarios = st.text_area(
                    "Applicable Scenarios",
                    key=f"share_scenarios_{trial.id}",
                )
                share_doc_url = st.text_input(
                    "Knowledge Doc URL",
                    key=f"share_doc_url_{trial.id}",
                )
                share_by = st.text_input(
                    "Shared by",
                    value=trial.owner,
                    key=f"share_by_{trial.id}",
                )

                if st.button("Create Share", key=f"create_share_{trial.id}"):
                    if not share_title.strip():
                        st.warning("Please enter a title.")
                    else:
                        share = Share(
                            trial_id=trial.id,
                            title=share_title.strip(),
                            summary=share_summary.strip() or None,
                            key_findings=share_findings.strip() or None,
                            reusable_patterns=share_patterns.strip() or None,
                            applicable_scenarios=share_scenarios.strip() or None,
                            knowledge_doc_url=share_doc_url.strip() or None,
                            shared_by=share_by.strip() or None,
                        )
                        _share_repo.create(share)

                        # Update trial status to shared
                        trial.status = "shared"
                        _trial_repo.update(trial)

                        # Build graph: Project -> produced -> TeamAsset
                        build_share_graph(_session, share)

                        st.success(
                            f"Share record created for **{project_name}**. "
                            f"Trial updated to **shared**."
                        )
                        st.rerun()


# =========================================================================
# Tab 2: List all share archives with Markdown export
# =========================================================================
with tab_list:
    all_shares = _share_repo.list_all()

    # Apply filter
    if shared_by_filter.strip():
        all_shares = [
            s
            for s in all_shares
            if s.shared_by and shared_by_filter.strip().lower() in s.shared_by.lower()
        ]

    if not all_shares:
        st.info("No share records found.")
    else:
        st.caption(f"Showing {len(all_shares)} share(s)")

        for share in all_shares:
            trial = _trial_repo.get(share.trial_id)
            project = _project_repo.get(trial.project_id) if trial else None
            project_name = project.name if project else "Unknown Project"

            date_str = share.shared_at.strftime("%Y-%m-%d") if share.shared_at else "-"
            header = f"**{share.title}** — {share.shared_by or '-'} ({date_str})"

            with st.expander(header, expanded=False):
                # Project info
                if project:
                    st.markdown(f"**Project:** {project_name}")
                    st.markdown(f"[GitHub]({project.github_url})")

                # Share details
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Shared by:** {share.shared_by or '-'}")
                    st.markdown(f"**Shared at:** {date_str}")
                with col2:
                    if share.knowledge_doc_url:
                        st.markdown(f"[Doc URL]({share.knowledge_doc_url})")

                if share.summary:
                    st.markdown("**Summary:**")
                    st.markdown(f"> {share.summary}")

                if share.key_findings:
                    st.markdown("**Key Findings:**")
                    st.markdown(share.key_findings)

                if share.reusable_patterns:
                    st.markdown("**Reusable Patterns:**")
                    st.markdown(share.reusable_patterns)

                if share.applicable_scenarios:
                    st.markdown("**Applicable Scenarios:**")
                    st.markdown(share.applicable_scenarios)

                # Markdown export
                st.divider()
                if st.button("Export Markdown", key=f"export_md_{share.id}"):
                    md = export_share_markdown(_session, share.id)
                    if md:
                        st.code(md, language="markdown")
                        st.download_button(
                            "Download Markdown",
                            data=md,
                            file_name=f"{share.title.replace(' ', '_')}.md",
                            mime="text/markdown",
                            key=f"download_md_{share.id}",
                        )
                    else:
                        st.error("Failed to generate Markdown.")
