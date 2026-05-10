"""Tests for state machine module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.models import Evaluation, Trial
from src.services.state_machine import (
    InvalidTransitionError,
    PreconditionFailedError,
    TRIAL_ALL_STATUSES,
    TRIAL_STATUS_META,
    TRIAL_TRANSITIONS,
    apply_eval_transition,
    apply_trial_transition,
    can_create_trial,
    get_allowed_eval_transitions,
    get_allowed_trial_transitions,
    validate_eval_transition,
    validate_trial_transition,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _make_trial(status: str = "claimed", **kwargs) -> Trial:
    defaults = {
        "id": 1,
        "project_id": 1,
        "owner": "testuser",
        "status": status,
        "claimed_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return Trial(**defaults)


def _make_eval(decision: str = "needs_review", **kwargs) -> Evaluation:
    defaults = {
        "id": 1,
        "project_id": 1,
        "decision": decision,
        "evaluated_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return Evaluation(**defaults)


# ── Trial state machine tests ───────────────────────────────────────


class TestTrialTransitions:
    """Test trial state transitions."""

    def test_claimed_to_running(self) -> None:
        trial = _make_trial("claimed")
        error = validate_trial_transition(trial, "running")
        assert error is None

    def test_running_to_blocked(self) -> None:
        trial = _make_trial("running", blockers="Some blocker")
        error = validate_trial_transition(trial, "blocked")
        assert error is None

    def test_running_to_blocked_requires_blockers(self) -> None:
        trial = _make_trial("running", blockers=None)
        error = validate_trial_transition(trial, "blocked")
        assert error is not None
        assert "Blockers" in error

    def test_running_to_demo_done(self) -> None:
        trial = _make_trial("running", result_summary="Some result")
        error = validate_trial_transition(trial, "demo_done")
        assert error is None

    def test_running_to_demo_done_requires_result(self) -> None:
        trial = _make_trial("running", result_summary=None)
        error = validate_trial_transition(trial, "demo_done")
        assert error is not None
        assert "Result summary" in error

    def test_demo_done_to_shared(self) -> None:
        trial = _make_trial("demo_done", result_summary="Done")
        error = validate_trial_transition(trial, "shared")
        assert error is None

    def test_blocked_to_running(self) -> None:
        trial = _make_trial("blocked")
        error = validate_trial_transition(trial, "running")
        assert error is None

    def test_claimed_to_blocked_invalid(self) -> None:
        trial = _make_trial("claimed")
        error = validate_trial_transition(trial, "blocked")
        assert error is not None
        assert "Cannot go from" in error

    def test_shared_to_any_invalid(self) -> None:
        trial = _make_trial("shared")
        for status in TRIAL_ALL_STATUSES:
            if status == "shared":
                continue
            error = validate_trial_transition(trial, status)
            assert error is not None

    def test_dropped_to_claimed(self) -> None:
        trial = _make_trial("dropped")
        error = validate_trial_transition(trial, "claimed")
        assert error is None

    def test_same_status_noop(self) -> None:
        trial = _make_trial("running")
        error = validate_trial_transition(trial, "running")
        assert error is None

    def test_get_allowed_transitions_claimed(self) -> None:
        transitions = get_allowed_trial_transitions("claimed")
        targets = {t.target for t in transitions}
        assert "running" in targets
        assert "dropped" in targets
        assert "blocked" not in targets

    def test_get_allowed_transitions_running(self) -> None:
        transitions = get_allowed_trial_transitions("running")
        targets = {t.target for t in transitions}
        assert "blocked" in targets
        assert "demo_done" in targets
        assert "dropped" in targets

    def test_get_allowed_transitions_shared(self) -> None:
        transitions = get_allowed_trial_transitions("shared")
        assert len(transitions) == 0

    def test_apply_transition_success(self) -> None:
        trial = _make_trial("claimed")
        apply_trial_transition(trial, "running")
        assert trial.status == "running"

    def test_apply_transition_with_validation(self) -> None:
        trial = _make_trial("running", result_summary="Done")
        apply_trial_transition(trial, "demo_done")
        assert trial.status == "demo_done"

    def test_apply_transition_validation_failure(self) -> None:
        trial = _make_trial("running", result_summary=None)
        with pytest.raises(PreconditionFailedError):
            apply_trial_transition(trial, "demo_done")

    def test_apply_transition_invalid(self) -> None:
        trial = _make_trial("claimed")
        with pytest.raises(InvalidTransitionError):
            apply_trial_transition(trial, "demo_done")


# ── Evaluation state machine tests ──────────────────────────────────


class TestEvalTransitions:
    """Test evaluation decision transitions."""

    def test_needs_review_to_watch(self) -> None:
        eval_obj = _make_eval("needs_review")
        error = validate_eval_transition(eval_obj, "watch")
        assert error is None

    def test_needs_review_to_try(self) -> None:
        eval_obj = _make_eval("needs_review")
        error = validate_eval_transition(eval_obj, "try")
        assert error is None

    def test_needs_review_to_reject(self) -> None:
        eval_obj = _make_eval("needs_review")
        error = validate_eval_transition(eval_obj, "reject")
        assert error is None

    def test_watch_to_try(self) -> None:
        eval_obj = _make_eval("watch")
        error = validate_eval_transition(eval_obj, "try")
        assert error is None

    def test_watch_to_adopt(self) -> None:
        eval_obj = _make_eval("watch")
        error = validate_eval_transition(eval_obj, "adopt")
        assert error is None

    def test_try_to_shared_requires_trials(self) -> None:
        eval_obj = _make_eval("try")
        error = validate_eval_transition(eval_obj, "adopt")
        # This is handled at page level, state machine allows it
        assert error is None

    def test_reject_to_watch(self) -> None:
        eval_obj = _make_eval("reject")
        error = validate_eval_transition(eval_obj, "watch")
        assert error is None

    def test_adopt_to_reject_invalid(self) -> None:
        eval_obj = _make_eval("adopt")
        error = validate_eval_transition(eval_obj, "reject")
        assert error is not None
        assert "Cannot go from" in error

    def test_get_allowed_transitions_needs_review(self) -> None:
        transitions = get_allowed_eval_transitions("needs_review")
        targets = {t.target for t in transitions}
        assert "watch" in targets
        assert "try" in targets
        assert "reject" in targets

    def test_get_allowed_transitions_watch(self) -> None:
        transitions = get_allowed_eval_transitions("watch")
        targets = {t.target for t in transitions}
        assert "try" in targets
        assert "adopt" in targets
        assert "reject" in targets

    def test_get_allowed_transitions_adopt(self) -> None:
        transitions = get_allowed_eval_transitions("adopt")
        targets = {t.target for t in transitions}
        assert "watch" in targets
        assert "reject" not in targets

    def test_apply_transition_success(self) -> None:
        eval_obj = _make_eval("needs_review")
        apply_eval_transition(eval_obj, "try")
        assert eval_obj.decision == "try"

    def test_apply_transition_invalid(self) -> None:
        eval_obj = _make_eval("adopt")
        with pytest.raises(InvalidTransitionError):
            apply_eval_transition(eval_obj, "reject")


# ── Cross-entity validation tests ───────────────────────────────────


class TestCrossEntityValidation:
    """Test cross-entity validation rules."""

    def test_can_create_trial_for_try(self) -> None:
        eval_obj = _make_eval("try")
        can, error = can_create_trial(eval_obj)
        assert can is True
        assert error == ""

    def test_cannot_create_trial_for_watch(self) -> None:
        eval_obj = _make_eval("watch")
        can, error = can_create_trial(eval_obj)
        assert can is False
        assert "try" in error

    def test_cannot_create_trial_for_reject(self) -> None:
        eval_obj = _make_eval("reject")
        can, error = can_create_trial(eval_obj)
        assert can is False
        assert "try" in error


# ── Status metadata tests ───────────────────────────────────────────


class TestStatusMetadata:
    """Test status metadata definitions."""

    def test_all_statuses_have_meta(self) -> None:
        for status in TRIAL_ALL_STATUSES:
            assert status in TRIAL_STATUS_META
            meta = TRIAL_STATUS_META[status]
            assert "emoji" in meta
            assert "color" in meta
            assert "label" in meta

    def test_all_statuses_have_transitions(self) -> None:
        for status in TRIAL_ALL_STATUSES:
            assert status in TRIAL_TRANSITIONS
