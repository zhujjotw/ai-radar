"""Trial management page: claim, track, and update trial status for projects."""

from __future__ import annotations

import streamlit as st

from src.db import get_session, init_db
from src.models import Trial
from src.repositories import EvaluationRepository, ProjectRepository, TrialRepository

# Status flow: claimed → running → blocked / demo_done → shared / dropped
VALID_STATUSES = ["claimed", "running", "blocked", "demo_done", "shared", "dropped"]

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)
_evaluation_repo = EvaluationRepository(_session)
_trial_repo = TrialRepository(_session)

# --- Page header ---
st.title("Trials")
st.caption("Claim projects for trial, track progress, and record outcomes")

# --- Sidebar filters ---
with st.sidebar:
    st.header("Trial Filters")

    status_filter = st.selectbox(
        "Status",
        options=["All"] + VALID_STATUSES,
        index=0,
    )

    owner_filter = st.text_input("Owner", value="")

st.divider()

# --- Tab layout ---
tab_claims, tab_active = st.tabs(["Claim Project", "Manage Trials"])

# =========================================================================
# Tab 1: Claim a project (create a Trial for projects with decision="try")
# =========================================================================
with tab_claims:
    st.subheader("Projects Marked for Trial (decision=try)")

    try_projects = _project_repo.list_with_options(decision="try")
    if not try_projects:
        st.info("No projects with decision='try'. Set a project to 'try' in the Radar page first.")
    else:
        for project in try_projects:
            existing_trials = _trial_repo.list_by_project(project.id) if project.id else []
            has_active_trial = any(t.status not in ("dropped", "shared") for t in existing_trials)

            eval_data = _evaluation_repo.get_latest_by_project(project.id) if project.id else None

            header = f"**{project.name}** ⭐{project.stars}"
            if eval_data and eval_data.recommendation_score:
                header += f" (rec: {eval_data.recommendation_score})"

            with st.expander(header, expanded=False):
                # Project info
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Pool:** {project.pool}")
                    st.markdown(f"**Source:** {project.source}")
                with col2:
                    st.markdown(f"**Stars:** {project.stars}")
                    st.markdown(f"**Language:** {project.language or '-'}")

                if project.description:
                    st.markdown(f"> {project.description}")
                if project.tags:
                    st.markdown("**Tags:** " + ", ".join(project.tags))

                st.markdown(f"[View on GitHub]({project.github_url})")

                # Existing trials
                if existing_trials:
                    st.divider()
                    st.markdown(f"**Existing trials:** {len(existing_trials)}")
                    for t in existing_trials:
                        st.markdown(
                            f"- {t.owner}: **{t.status}** "
                            f"(claimed {t.claimed_at.strftime('%Y-%m-%d')})"
                        )

                # Claim form
                st.divider()
                if has_active_trial:
                    st.info("This project already has an active trial.")
                else:
                    st.markdown("##### Claim This Project")
                    claim_owner = st.text_input(
                        "Your name",
                        key=f"claim_owner_{project.id}",
                    )
                    claim_due = st.date_input(
                        "Due date (optional)",
                        value=None,
                        key=f"claim_due_{project.id}",
                    )

                    if st.button("Claim", key=f"claim_{project.id}"):
                        if not claim_owner.strip():
                            st.warning("Please enter your name.")
                        else:
                            trial = Trial(
                                project_id=project.id,
                                owner=claim_owner.strip(),
                                status="claimed",
                                due_date=claim_due,
                            )
                            _trial_repo.create(trial)
                            st.success(
                                f"Claimed **{project.name}** for trial by {claim_owner.strip()}"
                            )
                            st.rerun()


# =========================================================================
# Tab 2: Manage existing trials — update status and fields
# =========================================================================
with tab_active:
    # Fetch trials based on filters
    all_trials = _trial_repo.list_all()

    # Apply filters
    if status_filter != "All":
        all_trials = [t for t in all_trials if t.status == status_filter]
    if owner_filter.strip():
        all_trials = [t for t in all_trials if owner_filter.strip().lower() in t.owner.lower()]

    if not all_trials:
        st.info("No trials match the current filters.")
    else:
        st.caption(f"Showing {len(all_trials)} trial(s)")

        for trial in all_trials:
            project = _project_repo.get(trial.project_id) if trial.project_id else None
            project_name = project.name if project else "Unknown Project"

            status_emoji = {
                "claimed": "🆕",
                "running": "🔄",
                "blocked": "🚫",
                "demo_done": "✅",
                "shared": "📤",
                "dropped": "❌",
            }.get(trial.status, "❓")

            due_str = f" (due {trial.due_date})" if trial.due_date else ""
            header = f"{status_emoji} **{project_name}** — {trial.owner} [{trial.status}]{due_str}"

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

                # Status transition
                st.divider()
                st.markdown("##### Update Status")

                # Determine allowed transitions
                allowed_next = {
                    "claimed": ["running", "dropped"],
                    "running": ["blocked", "demo_done", "dropped"],
                    "blocked": ["running", "dropped"],
                    "demo_done": ["shared", "dropped"],
                    "shared": [],
                    "dropped": ["claimed"],
                }
                next_statuses = allowed_next.get(trial.status, [])
                current_idx = (
                    VALID_STATUSES.index(trial.status) if trial.status in VALID_STATUSES else 0
                )

                if next_statuses:
                    new_status = st.selectbox(
                        "New status",
                        options=next_statuses,
                        key=f"status_{trial.id}",
                    )

                    # Additional fields for specific transitions
                    blockers_input = None
                    if new_status == "blocked":
                        blockers_input = st.text_area(
                            "Blockers (required)",
                            value=trial.blockers or "",
                            key=f"blockers_{trial.id}",
                        )
                    elif new_status == "demo_done":
                        st.warning("Trial must have a result summary before marking demo_done.")

                    drop_reason = None
                    if new_status == "dropped":
                        drop_reason = st.text_input(
                            "Drop reason",
                            key=f"drop_reason_{trial.id}",
                        )

                    if st.button("Update Status", key=f"update_status_{trial.id}"):
                        if new_status == "blocked" and not blockers_input.strip():
                            st.warning("Please describe what is blocking progress.")
                        elif new_status == "demo_done" and not trial.result_summary:
                            st.warning(
                                "Please fill in the Result Summary below "
                                "before marking as demo_done."
                            )
                        else:
                            trial.status = new_status
                            if blockers_input is not None:
                                trial.blockers = blockers_input.strip() or None
                            if drop_reason is not None:
                                trial.trial_notes = (
                                    (trial.trial_notes or "") + f"\n[Dropped: {drop_reason}]"
                                ).strip()
                            _trial_repo.update(trial)
                            st.success(f"Status updated to **{new_status}**")
                            st.rerun()
                else:
                    st.info(f"No further transitions available from **{trial.status}**.")

                # Editable fields
                st.divider()
                st.markdown("##### Trial Details")

                edit_owner = st.text_input(
                    "Owner",
                    value=trial.owner,
                    key=f"edit_owner_{trial.id}",
                )
                edit_due = st.date_input(
                    "Due date",
                    value=trial.due_date,
                    key=f"edit_due_{trial.id}",
                )
                edit_env = st.text_input(
                    "Environment",
                    value=trial.environment or "",
                    key=f"edit_env_{trial.id}",
                )
                edit_demo_url = st.text_input(
                    "Demo URL",
                    value=trial.demo_url or "",
                    key=f"edit_demo_{trial.id}",
                )
                edit_notes = st.text_area(
                    "Trial Notes",
                    value=trial.trial_notes or "",
                    key=f"edit_notes_{trial.id}",
                )
                edit_result = st.text_area(
                    "Result Summary",
                    value=trial.result_summary or "",
                    key=f"edit_result_{trial.id}",
                )
                edit_next = st.text_input(
                    "Next Action",
                    value=trial.next_action or "",
                    key=f"edit_next_{trial.id}",
                )

                if st.button("Save Details", key=f"save_details_{trial.id}"):
                    trial.owner = edit_owner.strip()
                    trial.due_date = edit_due
                    trial.environment = edit_env.strip() or None
                    trial.demo_url = edit_demo_url.strip() or None
                    trial.trial_notes = edit_notes.strip() or None
                    trial.result_summary = edit_result.strip() or None
                    trial.next_action = edit_next.strip() or None
                    _trial_repo.update(trial)
                    st.success("Trial details saved.")
                    st.rerun()
