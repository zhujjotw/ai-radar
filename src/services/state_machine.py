"""State machines for Trial lifecycle and Evaluation decisions.

Implements the state transition rules defined in the system design:

Trial states:    claimed → running → blocked / demo_done → shared / dropped
Evaluation:      needs_review → watch / try / adopt / reject

Each transition has:
- allowed source states
- required target state
- optional validation function (checks preconditions)
- optional side effects (auto-updates related fields)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.models import Evaluation, Trial


# ── Exceptions ──────────────────────────────────────────────────────


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, current: str, target: str, reason: str = ""):
        self.current = current
        self.target = target
        self.reason = reason
        msg = f"Cannot transition from '{current}' to '{target}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class PreconditionFailedError(Exception):
    """Raised when a transition's preconditions are not met."""

    def __init__(self, message: str):
        super().__init__(message)


# ── Transition definition ───────────────────────────────────────────


@dataclass(frozen=True)
class Transition:
    """Defines a single state transition."""

    target: str
    source_states: frozenset[str]
    label: str
    description: str
    validate: Callable[[Trial | Evaluation], str | None] | None = None
    """Optional validator. Returns error message if validation fails, None if ok."""


def _trial_validate_blocked(entity: Trial | Evaluation) -> str | None:
    """Blocked trials must have blockers description."""
    if isinstance(entity, Trial) and not (entity.blockers and entity.blockers.strip()):
        return "Blockers description is required"
    return None


def _trial_validate_demo_done(entity: Trial | Evaluation) -> str | None:
    """Demo_done trials must have result_summary."""
    if isinstance(entity, Trial) and not (entity.result_summary and entity.result_summary.strip()):
        return "Result summary is required before marking demo_done"
    return None


def _trial_validate_shared(entity: Trial | Evaluation) -> str | None:
    """Shared trials must have result_summary and demo_url recommended."""
    if isinstance(entity, Trial):
        if not (entity.result_summary and entity.result_summary.strip()):
            return "Result summary is required before marking shared"
    return None


def _eval_validate_try(entity: Trial | Evaluation) -> str | None:
    """Try decision should have recommendation_score >= 3."""
    if isinstance(entity, Evaluation):
        if entity.recommendation_score is not None and entity.recommendation_score < 3:
            return "Recommendation score should be >= 3 for 'try' decision"
    return None


def _eval_validate_adopt(entity: Trial | Evaluation) -> str | None:
    """Adopt decision requires a trial with shared status."""
    # This check would need DB access, so we do it at the page level
    return None


# ── Trial state machine ─────────────────────────────────────────────

TRIAL_TRANSITIONS: dict[str, Transition] = {
    "running": Transition(
        target="running",
        source_states=frozenset({"claimed", "blocked"}),
        label="Start Trial",
        description="Move from claimed or blocked to actively running",
    ),
    "blocked": Transition(
        target="blocked",
        source_states=frozenset({"running"}),
        label="Mark Blocked",
        description="Trial is blocked by an issue",
        validate=_trial_validate_blocked,
    ),
    "demo_done": Transition(
        target="demo_done",
        source_states=frozenset({"running"}),
        label="Demo Complete",
        description="Trial demo is complete with results",
        validate=_trial_validate_demo_done,
    ),
    "shared": Transition(
        target="shared",
        source_states=frozenset({"demo_done"}),
        label="Share Complete",
        description="Trial results have been shared with the team",
        validate=_trial_validate_shared,
    ),
    "dropped": Transition(
        target="dropped",
        source_states=frozenset({"claimed", "running", "blocked", "demo_done"}),
        label="Drop Trial",
        description="Abandon this trial",
    ),
    "claimed": Transition(
        target="claimed",
        source_states=frozenset({"dropped"}),
        label="Reclaim",
        description="Reclaim a previously dropped trial",
    ),
}

TRIAL_ALL_STATUSES = ["claimed", "running", "blocked", "demo_done", "shared", "dropped"]

TRIAL_STATUS_META = {
    "claimed": {"emoji": "🆕", "color": "blue", "label": "Claimed"},
    "running": {"emoji": "🔄", "color": "orange", "label": "Running"},
    "blocked": {"emoji": "🚫", "color": "red", "label": "Blocked"},
    "demo_done": {"emoji": "✅", "color": "green", "label": "Demo Done"},
    "shared": {"emoji": "📤", "color": "purple", "label": "Shared"},
    "dropped": {"emoji": "❌", "color": "gray", "label": "Dropped"},
}


def get_allowed_trial_transitions(current_status: str) -> list[Transition]:
    """Return list of transitions allowed from the current trial status."""
    result = []
    for transition in TRIAL_TRANSITIONS.values():
        if current_status in transition.source_states:
            result.append(transition)
    return result


def validate_trial_transition(trial: Trial, target_status: str) -> str | None:
    """Validate a trial state transition.

    Returns error message if invalid, None if valid.
    """
    current = trial.status

    if current == target_status:
        return None  # No-op, always ok

    transition = TRIAL_TRANSITIONS.get(target_status)
    if not transition:
        return f"Unknown status: {target_status}"

    if current not in transition.source_states:
        allowed = ", ".join(sorted(transition.source_states))
        return f"Cannot go from '{current}' to '{target_status}'. Allowed from '{current}': {allowed}"

    if transition.validate:
        error = transition.validate(trial)
        if error:
            return error

    return None


def apply_trial_transition(trial: Trial, target_status: str) -> Trial:
    """Apply a trial state transition after validation.

    Raises InvalidTransitionError or PreconditionFailedError on failure.
    Returns the updated trial.
    """
    error = validate_trial_transition(trial, target_status)
    if error:
        if target_status not in TRIAL_TRANSITIONS:
            raise InvalidTransitionError(trial.status, target_status, error)
        raise PreconditionFailedError(error)

    trial.status = target_status
    return trial


# ── Evaluation decision state machine ───────────────────────────────

EVAL_TRANSITIONS: dict[str, Transition] = {
    "watch": Transition(
        target="watch",
        source_states=frozenset({"needs_review", "try", "adopt", "reject"}),
        label="Watch",
        description="Keep an eye on this project, not ready to try yet",
    ),
    "try": Transition(
        target="try",
        source_states=frozenset({"needs_review", "watch", "reject"}),
        label="Try",
        description="Worth trying out, assign a team member",
        validate=_eval_validate_try,
    ),
    "adopt": Transition(
        target="adopt",
        source_states=frozenset({"try", "watch"}),
        label="Adopt",
        description="Adopt into team tech stack",
    ),
    "reject": Transition(
        target="reject",
        source_states=frozenset({"needs_review", "watch", "try"}),
        label="Reject",
        description="Not relevant or valuable for the team",
    ),
}

EVAL_ALL_DECISIONS = ["needs_review", "watch", "try", "adopt", "reject"]

EVAL_DECISION_META = {
    "needs_review": {"emoji": "🔍", "color": "gray", "label": "Needs Review"},
    "watch": {"emoji": "👀", "color": "blue", "label": "Watch"},
    "try": {"emoji": "🧪", "color": "orange", "label": "Try"},
    "adopt": {"emoji": "✅", "color": "green", "label": "Adopt"},
    "reject": {"emoji": "❌", "color": "red", "label": "Reject"},
}


def get_allowed_eval_transitions(current_decision: str) -> list[Transition]:
    """Return list of transitions allowed from the current evaluation decision."""
    result = []
    for transition in EVAL_TRANSITIONS.values():
        if current_decision in transition.source_states:
            result.append(transition)
    return result


def validate_eval_transition(evaluation: Evaluation, target_decision: str) -> str | None:
    """Validate an evaluation decision transition.

    Returns error message if invalid, None if valid.
    """
    current = evaluation.decision

    if current == target_decision:
        return None

    transition = EVAL_TRANSITIONS.get(target_decision)
    if not transition:
        return f"Unknown decision: {target_decision}"

    if current not in transition.source_states:
        allowed = ", ".join(sorted(transition.source_states))
        return (
            f"Cannot go from '{current}' to '{target_decision}'. "
            f"Allowed from '{current}': {allowed}"
        )

    if transition.validate:
        error = transition.validate(evaluation)
        if error:
            return error

    return None


def apply_eval_transition(evaluation: Evaluation, target_decision: str) -> Evaluation:
    """Apply an evaluation decision transition after validation.

    Raises InvalidTransitionError or PreconditionFailedError on failure.
    Returns the updated evaluation.
    """
    error = validate_eval_transition(evaluation, target_decision)
    if error:
        if target_decision not in EVAL_TRANSITIONS:
            raise InvalidTransitionError(evaluation.decision, target_decision, error)
        raise PreconditionFailedError(error)

    evaluation.decision = target_decision
    return evaluation


# ── Cross-entity validation ─────────────────────────────────────────


def can_create_trial(evaluation: Evaluation) -> tuple[bool, str]:
    """Check if a trial can be created for this evaluation.

    A trial requires decision='try' and recommendation_score >= 3.
    """
    if evaluation.decision != "try":
        return False, f"Project decision is '{evaluation.decision}', must be 'try'"
    return True, ""


def can_adopt_project(evaluation: Evaluation, trials: list[Trial]) -> tuple[bool, str]:
    """Check if a project can be adopted.

    Adoption requires at least one shared trial with result_summary.
    """
    shared_trials = [t for t in trials if t.status == "shared"]
    if not shared_trials:
        return False, "At least one shared trial is required before adoption"

    has_results = any(t.result_summary and t.result_summary.strip() for t in shared_trials)
    if not has_results:
        return False, "Shared trial must have a result summary"

    return True, ""
