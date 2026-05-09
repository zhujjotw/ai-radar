"""Candidate Pool page: card-table view with expandable project details."""

from __future__ import annotations

import streamlit as st

from src.config import get_settings
from src.db import get_session, init_db
from src.models import Evaluation, Trial
from src.repositories import EvaluationRepository, ProjectRepository, TrialRepository
from src.services.state_machine import (
    EVAL_DECISION_META,
    apply_eval_transition,
    get_allowed_eval_transitions,
    validate_eval_transition,
)

# --- Database setup ---
init_db()
_session = get_session()
_project_repo = ProjectRepository(_session)
_evaluation_repo = EvaluationRepository(_session)
_trial_repo = TrialRepository(_session)

# --- Status badge colors ---
_STATUS_STYLE: dict[str, str] = {
    "needs_review": "color:#8b949e;",
    "watch": "color:#58a6ff;",
    "try": "color:#d29922;",
    "adopt": "color:#3fb950;",
    "reject": "color:#f85149;",
    "claimed": "color:#58a6ff;",
    "running": "color:#d29922;",
    "blocked": "color:#f85149;",
    "demo_done": "color:#3fb950;",
    "shared": "color:#a371f7;",
    "dropped": "color:#8b949e;",
}

# --- Page header ---
st.title("Candidate Pool")
st.caption("AI 开源项目候选池 — 浏览、评估、认领")

# --- Filters ---
st.subheader("筛选")
filter_cols = st.columns(4)

with filter_cols[0]:
    pool_filter = st.selectbox(
        "Pool",
        options=["All", "baseline", "candidate"],
        index=0,
    )
with filter_cols[1]:
    filter_status_filter = st.selectbox(
        "Filter Status",
        options=["All", "needs_review", "passed", "filtered_out", "override"],
        index=0,
    )
with filter_cols[2]:
    source_filter = st.selectbox(
        "Source",
        options=["All", "baseline", "github_search", "external", "manual"],
        index=0,
    )
with filter_cols[3]:
    all_tags = _project_repo.get_all_tags()
    tag_filter = st.selectbox(
        "方向",
        options=["全部方向"] + all_tags,
        index=0,
    )

# Sort options
sort_options = {
    "推荐分优先": ("recommendation_sort", True),
    "Stars 最多": ("stars", True),
    "最新发现": ("first_seen_at", True),
    "最近更新": ("last_pushed_at", True),
    "未评估优先": ("unevaluated_sort", True),
}
sort_label = st.selectbox("排序", options=list(sort_options.keys()), index=0)

st.divider()

# --- Load settings early for sidebar LLM config ---
_settings = get_settings()
_llm_configured = bool(_settings.llm_api_key)

# --- Sidebar LLM config ---
with st.sidebar:
    st.header("LLM 配置")

    llm_api_key = st.text_input(
        "API Key",
        value=_settings.llm_api_key or "",
        type="password",
        key="sidebar_llm_api_key",
    )
    llm_base_url = st.text_input(
        "Base URL",
        value=_settings.llm_base_url,
        key="sidebar_llm_base_url",
    )
    llm_model = st.text_input(
        "Model",
        value=_settings.llm_model,
        key="sidebar_llm_model",
    )
    if st.button("保存 LLM 配置", key="save_llm_config"):
        env_path = _settings.model_config.get("env_file")
        if env_path:
            lines = []
            existing = {}
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#") and "=" in stripped:
                            k, _, v = stripped.partition("=")
                            existing[k.strip()] = v.strip()
            except FileNotFoundError:
                pass
            existing["LLM_API_KEY"] = llm_api_key.strip()
            existing["LLM_BASE_URL"] = llm_base_url.strip()
            existing["LLM_MODEL"] = llm_model.strip()
            with open(env_path, "w", encoding="utf-8") as f:
                for k, v in existing.items():
                    f.write(f"{k}={v}\n")
            st.success("LLM 配置已保存到 .env，下次启动生效")

st.divider()

# --- Fetch projects ---
kw: dict = {}
if pool_filter != "All":
    kw["pool"] = pool_filter
if filter_status_filter != "All":
    kw["filter_status"] = filter_status_filter
if source_filter != "All":
    kw["source"] = source_filter
if tag_filter != "全部方向":
    kw["tag"] = tag_filter

order_key, order_desc = sort_options[sort_label]

if order_key in ("recommendation_sort", "unevaluated_sort"):
    projects = _project_repo.list_with_options(**{k: v for k, v in kw.items() if k != "order_by"})
else:
    projects = _project_repo.list_with_options(
        **{k: v for k, v in kw.items() if k != "order_by"},
        order_by=order_key,
        order_desc=order_desc,
    )

# In-memory sorting for special sort modes
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

# --- Pre-load trial data for all projects ---
_trial_cache: dict[int, list[Trial]] = {}
for p in projects:
    if p.id and p.id not in _trial_cache:
        _trial_cache[p.id] = _trial_repo.list_by_project(p.id)


def _get_owner(project_id: int | None) -> str:
    if not project_id:
        return ""
    trials = _trial_cache.get(project_id, [])
    active = [t for t in trials if t.status not in ("dropped",)]
    if active:
        return active[-1].owner
    return ""


def _get_status_display(project_id: int | None, evaluation: Evaluation | None) -> tuple[str, str]:
    if not project_id:
        return "-", ""
    trials = _trial_cache.get(project_id, [])
    active = [t for t in trials if t.status not in ("dropped",)]
    if active:
        status = active[-1].status
        return status, _STATUS_STYLE.get(status, "")
    if evaluation:
        return evaluation.decision, _STATUS_STYLE.get(evaluation.decision, "")
    return "-", ""


def _has_active_trial(project_id: int | None) -> bool:
    if not project_id:
        return False
    return any(t.status not in ("dropped", "shared") for t in _trial_cache.get(project_id, []))


def _render_score_bar(score: int | None, max_score: int = 5) -> str:
    if score is None:
        return "-"
    filled = "●" * score
    empty = "○" * (max_score - score)
    return f"{filled}{empty} {score}/{max_score}"


# --- Display project cards ---
if not projects:
    st.info("没有匹配的项目。")
else:
    st.caption(f"共 {len(projects)} 个项目")

    for project in projects:
        evaluation = _evaluation_repo.get_latest_by_project(project.id) if project.id else None
        owner = _get_owner(project.id)
        status_label, status_style = _get_status_display(project.id, evaluation)

        # Build expander header
        tags_str = " · ".join(project.tags) if project.tags else ""
        rec_score = evaluation.recommendation_score if evaluation else None
        score_str = f"{rec_score}/5" if rec_score is not None else "-"
        owner_str = owner or "未认领"

        header = (
            f"{project.name}  "
            f"{'`' + tags_str + '`  ' if tags_str else ''}"
            f"{score_str}  "
            f"{owner_str}  "
        )

        with st.expander(header, expanded=False):
            # ---- Project Info ----
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.markdown(f"**Stars:** {project.stars:,}")
                st.markdown(f"**Forks:** {project.forks:,}")
                st.markdown(f"**Open Issues:** {project.open_issues:,}")
            with col_b:
                st.markdown(f"**Language:** {project.language or '-'}")
                st.markdown(f"**License:** {project.license or '-'}")
                st.markdown(f"**Pool:** {project.pool}")
            with col_c:
                st.markdown(f"**Source:** {project.source}")
                if project.last_pushed_at:
                    st.markdown(f"**Last Push:** {project.last_pushed_at.strftime('%Y-%m-%d')}")
                if project.first_seen_at:
                    st.markdown(f"**Discovered:** {project.first_seen_at.strftime('%Y-%m-%d')}")

            # GitHub description
            if project.description:
                st.markdown(f"> {project.description}")

            # Tags & Topics
            tag_col, topic_col = st.columns(2)
            with tag_col:
                if project.tags:
                    st.markdown("**方向标签:** " + " · ".join(project.tags))
            with topic_col:
                if project.topics:
                    st.markdown("**GitHub Topics:** " + " · ".join(project.topics))

            # GitHub link
            st.markdown(f"[View on GitHub]({project.github_url})")

            if project.llm_description:
                st.divider()
                st.markdown(f"**项目描述:** {project.llm_description}")
                if project.llm_scenarios:
                    st.markdown(f"**适用场景:**\n{project.llm_scenarios}")

            # ---- Evaluation Info ----
            if evaluation:
                st.divider()
                st.markdown("##### 评估信息")
                eval_cols = st.columns(5)
                eval_cols[0].metric("相关性", evaluation.relevance_score or "-")
                eval_cols[1].metric("可试用性", evaluation.trialability_score or "-")
                eval_cols[2].metric("业务价值", evaluation.value_score or "-")
                eval_cols[3].metric("推荐分", evaluation.recommendation_score or "-")
                eval_cols[4].metric("决策", evaluation.decision)
                if evaluation.evidence:
                    st.caption(evaluation.evidence)
                if evaluation.decision_reason:
                    st.caption(f"原因: {evaluation.decision_reason}")

            # ---- Trial Info ----
            trials = _trial_cache.get(project.id, [])
            active_trials = [t for t in trials if t.status not in ("dropped",)]
            if active_trials:
                st.divider()
                st.markdown("##### 试用信息")
                for t in active_trials:
                    t_cols = st.columns([2, 2, 2, 2])
                    t_cols[0].markdown(f"**负责人:** {t.owner}")
                    t_cols[1].markdown(f"**状态:** {t.status}")
                    if t.due_date:
                        t_cols[2].markdown(f"**截止日期:** {t.due_date}")
                    if t.environment:
                        t_cols[3].markdown(f"**环境:** {t.environment}")
                    if t.trial_notes:
                        st.markdown(f"**备注:** {t.trial_notes}")
                    if t.result_summary:
                        st.markdown(f"**结果摘要:** {t.result_summary}")
                    if t.blockers:
                        st.markdown(f"**阻塞项:** {t.blockers}")

            # ---- Actions ----
            st.divider()

            action_col1, action_col2, action_col3 = st.columns(3)

            with action_col1:
                st.markdown("##### 认领项目")
                if _has_active_trial(project.id):
                    st.info(f"已由 {owner} 认领")
                    if st.button("前往 Trials 管理", key=f"goto_trial_{project.id}"):
                        st.switch_page("pages/trials.py")
                else:
                    claim_owner = st.text_input(
                        "你的名字",
                        key=f"claim_owner_{project.id}",
                    )
                    if st.button("认领", key=f"claim_{project.id}"):
                        if not claim_owner.strip():
                            st.warning("请输入你的名字")
                        else:
                            if not evaluation or evaluation.decision != "try":
                                if evaluation:
                                    evaluation.decision = "try"
                                    _evaluation_repo.update(evaluation)
                                else:
                                    new_eval = Evaluation(project_id=project.id, decision="try")
                                    _evaluation_repo.create(new_eval)
                            trial = Trial(
                                project_id=project.id,
                                owner=claim_owner.strip(),
                                status="claimed",
                            )
                            _trial_repo.create(trial)
                            st.success(f"已认领 **{project.name}**")
                            st.rerun()

            with action_col2:
                st.markdown("##### 设决策")
                current_decision = evaluation.decision if evaluation else "needs_review"

                # Get allowed transitions from state machine
                if current_decision == "needs_review":
                    # New evaluation - can choose any decision
                    allowed_decisions = ["watch", "try", "reject"]
                else:
                    allowed_transitions = get_allowed_eval_transitions(current_decision)
                    allowed_decisions = [t.target for t in allowed_transitions]

                if allowed_decisions:
                    # Build options with labels
                    decision_options = {}
                    for d in allowed_decisions:
                        meta = EVAL_DECISION_META.get(d, {})
                        label = meta.get("label", d)
                        emoji = meta.get("emoji", "")
                        decision_options[d] = f"{emoji} {label}"

                    new_decision = st.selectbox(
                        "决策",
                        options=allowed_decisions,
                        format_func=lambda x: decision_options.get(x, x),
                        index=allowed_decisions.index(current_decision)
                        if current_decision in allowed_decisions
                        else 0,
                        key=f"decision_{project.id}",
                    )

                    # Show validation feedback
                    if evaluation and current_decision != "needs_review":
                        validation_error = validate_eval_transition(evaluation, new_decision)
                        if validation_error:
                            st.warning(f"⚠️ {validation_error}")

                    decision_reason = st.text_input(
                        "原因",
                        value=evaluation.decision_reason or "" if evaluation else "",
                        key=f"reason_{project.id}",
                    )
                    if st.button("保存决策", key=f"save_decision_{project.id}"):
                        try:
                            if evaluation and current_decision != "needs_review":
                                # Use state machine for existing evaluations
                                evaluation.decision_reason = decision_reason or None
                                apply_eval_transition(evaluation, new_decision)
                                _evaluation_repo.update(evaluation)
                            elif evaluation:
                                # Update existing evaluation from needs_review
                                evaluation.decision = new_decision
                                evaluation.decision_reason = decision_reason or None
                                _evaluation_repo.update(evaluation)
                            else:
                                # Create new evaluation
                                new_eval = Evaluation(
                                    project_id=project.id,
                                    decision=new_decision,
                                    decision_reason=decision_reason or None,
                                )
                                _evaluation_repo.create(new_eval)
                            st.success(f"决策已设为 **{new_decision}**")
                            st.rerun()
                        except Exception as e:
                            st.error(f"决策更新失败: {e}")
                else:
                    st.info(f"当前决策 **{current_decision}** 不可更改")

            with action_col3:
                st.markdown("##### 覆盖过滤")
                if project.filter_status != "override":
                    override_reason = st.text_input(
                        "覆盖原因",
                        key=f"override_reason_{project.id}",
                    )
                    if st.button("覆盖过滤", key=f"override_{project.id}"):
                        if not override_reason:
                            st.warning("请输入覆盖原因")
                        else:
                            project.filter_status = "override"
                            project.filter_reason = override_reason
                            _project_repo.update(project)
                            st.success("已覆盖过滤")
                            st.rerun()
                else:
                    st.info(f"已覆盖: {project.filter_reason or '无原因'}")
                    if st.button("取消覆盖", key=f"remove_override_{project.id}"):
                        project.filter_status = "needs_review"
                        project.filter_reason = None
                        _project_repo.update(project)
                        st.success("已取消覆盖")
                        st.rerun()
