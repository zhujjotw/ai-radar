"""State machines for Trial lifecycle and Evaluation decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import Evaluation, Trial


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


@dataclass(frozen=True)
class Transition:
    """Defines a single state transition."""

    target: str
    source_states: frozenset[str]
    label: str
    description: str
    validate: Callable[[Trial | Evaluation], str | None] | None = None


def _trial_validate_blocked(entity: Trial | Evaluation) -> str | None:
    if isinstance(entity, Trial) and not (entity.blockers and entity.blockers.strip()):
        return "Blockers description is required"
    return None


def _trial_validate_demo_done(entity: Trial | Evaluation) -> str | None:
    if isinstance(entity, Trial) and not (entity.result_summary and entity.result_summary.strip()):
        return "Result summary is required before marking demo_done"
    return None


def _trial_validate_shared(entity: Trial | Evaluation) -> str | None:
    if isinstance(entity, Trial):
        if not (entity.result_summary and entity.result_summary.strip()):
            return "Result summary is required before marking shared"
    return None


def _eval_validate_try(entity: Trial | Evaluation) -> str | None:
    if isinstance(entity, Evaluation):
        if entity.recommendation_score is not None and entity.recommendation_score < 3:
            return "Recommendation score should be >= 3 for 'try' decision"
    return None


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
    result = []
    for transition in TRIAL_TRANSITIONS.values():
        if current_status in transition.source_states:
            result.append(transition)
    return result


def validate_trial_transition(trial: Trial, target_status: str) -> str | None:
    current = trial.status
    if current == target_status:
        return None
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
    error = validate_trial_transition(trial, target_status)
    if error:
        if target_status not in TRIAL_TRANSITIONS:
            raise InvalidTransitionError(trial.status, target_status, error)
        raise PreconditionFailedError(error)
    trial.status = target_status
    return trial


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
    result = []
    for transition in EVAL_TRANSITIONS.values():
        if current_decision in transition.source_states:
            result.append(transition)
    return result


def validate_eval_transition(evaluation: Evaluation, target_decision: str) -> str | None:
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
    error = validate_eval_transition(evaluation, target_decision)
    if error:
        if target_decision not in EVAL_TRANSITIONS:
            raise InvalidTransitionError(evaluation.decision, target_decision, error)
        raise PreconditionFailedError(error)
    evaluation.decision = target_decision
    return evaluation


def can_create_trial(evaluation: Evaluation) -> tuple[bool, str]:
    if evaluation.decision != "try":
        return False, f"Project decision is '{evaluation.decision}', must be 'try'"
    return True, ""


def can_adopt_project(evaluation: Evaluation, trials: list[Trial]) -> tuple[bool, str]:
    shared_trials = [t for t in trials if t.status == "shared"]
    if not shared_trials:
        return False, "At least one shared trial is required before adoption"
    has_results = any(t.result_summary and t.result_summary.strip() for t in shared_trials)
    if not has_results:
        return False, "Shared trial must have a result summary"
    return True, ""
