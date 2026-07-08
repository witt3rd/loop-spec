"""
loop_spec — Python implementation of the loop-spec specification.

Provides Pydantic models for all six loop kinds and load_spec() for
validating YAML spec files against the schema.

Usage:
    from loop_spec import load_spec, MetricOptimizationSpec

    spec = load_spec("path/to/spec.yaml")
    assert isinstance(spec, MetricOptimizationSpec)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Git URL validation
# ---------------------------------------------------------------------------

_GIT_URL_RE = re.compile(
    r"^(https?|git|ssh|file)://"  # scheme-based URLs
    r"|^git@"                      # SCP-style SSH (git@github.com:org/repo.git)
)


def _is_git_url(value: str) -> bool:
    return bool(_GIT_URL_RE.match(value))


# ---------------------------------------------------------------------------
# ExecutorSpec — how the agent is invoked (closes the "handoff is a file" gap)
# ---------------------------------------------------------------------------


class ExecutorSpec(BaseModel):
    """Declares who — or what — takes the action on each turn.

    An executor receives the turn's context, takes an action in the world, and
    returns a ``TurnResult``. That contract is executor-agnostic: a shell script
    satisfies it deterministically, a Hermes agent satisfies it with reasoning,
    an HTTP service satisfies it over the wire — and a human satisfies it with
    judgment. The ``human`` type is not a degenerate case; it is the general
    case the others specialize.

    The ``human`` type is also what lets a loop's action be handed off over
    time: a loop can begin ``human`` (a person does the turns), graduate to
    ``hermes`` at ``level: L1`` (agent proposes, human reviews every turn), then
    L2, then L3 (autonomous). The executor type names *who acts*; ``level`` names
    *how much they are trusted*. Together they encode the full handoff arc.

    Types:
        human   — a person takes the turn (requires ``who``)
        hermes  — Hermes agent profile (requires ``profile``)
        shell   — arbitrary executable with LOOP_* env vars (requires ``command``)
        http    — POST TurnContext JSON, receive TurnResult JSON (requires ``url``)

    Machine executors (hermes, shell, http) are external processes — they do
    not import the loop-spec SDK. The execution fabric (e.g. Saturate) launches
    them, monitors them, and recovers from crashes. A ``human`` executor is not
    launched by the fabric; the fabric surfaces the turn's context and waits for
    the human to record a ``TurnResult``.
    """

    type: Literal["human", "hermes", "shell", "http"] = "shell"
    who: str | None = None      # human: identifier of the person taking the turn
    profile: str | None = None  # hermes: agent profile name
    command: str | None = None  # shell: executable + args
    url: str | None = None      # http: POST endpoint


class TurnResult(BaseModel):
    """The outcome of a single executor turn.

    Every executor — shell, hermes, http, or human — returns a ``TurnResult``
    describing what actually happened when it acted on the turn's context. The
    outcome vocabulary is deliberately richer than pass/fail: an executor that
    could only ever report success would hide exactly the signal the loop needs
    in order to learn — where the proposed action was wrong. Non-compliance is
    a first-class, expected result, not an error.

    Outcomes:
        applied   — executed the proposed action as-is
        modified  — executed a changed version of the proposal (the estimate was
                    close, but the executor had better local information)
        rejected  — declined to act. The highest-signal outcome: the proposal
                    was made and refused, which means either the proposal was
                    wrong or the executor holds out-of-band knowledge the loop
                    does not have. Either way it is training data.
        failed    — attempted the action and did not complete it
    """

    outcome: Literal["applied", "modified", "rejected", "failed"]
    notes: str | None = None
    """Free-text account of the turn. For ``modified`` and ``rejected`` this is
    the training signal — *why* the executor diverged from the proposed action.
    """
    metric_value: float | None = None
    """Measured metric after the turn, if the loop is metric-shaped. ``None``
    for loops with no scalar metric.
    """


# ---------------------------------------------------------------------------
# Terminal conditions — shared across all loop kinds
# ---------------------------------------------------------------------------


class TerminalConditions(BaseModel):
    """Conditions under which a loop terminates.

    max_iterations is required — no open-ended loops.
    plateau_count and target_score are optional but recommended.
    """

    max_iterations: int = 100
    plateau_count: int = 10
    target_score: float | None = None


# ---------------------------------------------------------------------------
# Base spec — fields common to all loop kinds
# ---------------------------------------------------------------------------


class LoopSpec(BaseModel):
    """Base class for all loop specs. Not instantiated directly."""

    model_config = {"extra": "forbid"}

    kind: str
    name: str
    level: Literal["L1", "L2", "L3"] = "L1"
    terminal: TerminalConditions = Field(default_factory=TerminalConditions)
    executor: ExecutorSpec | None = None
    """How the agent executor is invoked each turn.

    ``None`` means execution is handled externally by the consumer (e.g.
    Cyclus manages its own dispatch via ``delegate_task`` or ``hermes cron``).
    Execution fabrics like Saturate require an explicit executor declaration.
    """
    output_dir: str = "./output"
    """Directory where the loop writes completed artifacts and findings.

    Distinct from the running deliberation log (e.g. STATE.md used by
    Cyclus workers). ``output_dir`` is where *finished* work accumulates;
    the deliberation log is where *in-progress* reasoning lives.
    """
    repo: str | None = None
    """Git URL of the repository the loop operates on.

    Must be a valid git URL: https://, git://, git@, ssh://, or file://.

    The execution fabric (e.g. Saturate) clones this URL into an isolated
    worktree, scopes all hypothesis commits and reverts to that worktree,
    and never touches the fabric's own source tree.

    Credentials are a deployment concern — the fabric runs in an environment
    with pre-configured access (SSH key, GITHUB_TOKEN, etc.), exactly as a
    CI runner would.

    ``None`` means the loop produces no git-backed hypothesis commits (e.g.
    Cyclus delegate_task loops, L1 report-only loops).
    """

    @field_validator("repo")
    @classmethod
    def _validate_repo_url(cls, v: str | None) -> str | None:
        if v is not None and not _is_git_url(v):
            raise ValueError(
                f"repo must be a git URL (https://, git://, git@, ssh://, file://), "
                f"got {v!r}"
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def _check_renamed_fields(cls, data: Any) -> Any:
        if isinstance(data, dict) and "memory" in data:
            raise ValueError(
                "The 'memory' field was renamed to 'output_dir' in loop-spec v0.2. "
                "Please update your spec file."
            )
        return data


# ---------------------------------------------------------------------------
# Six loop kinds
# ---------------------------------------------------------------------------


class MetricOptimizationSpec(LoopSpec):
    """Improve a numeric metric over iterations.

    Terminal: score exceeds target_score OR plateau_count consecutive
    iterations with no improvement.

    The hypothesis/evaluate/keep-or-revert cycle:
      1. executor generates a hypothesis and applies it
      2. evaluate command runs and a scalar is extracted
      3. correctness command runs (if set) — must pass for the hypothesis to be kept
      4. if improved AND correct: commit; else revert
    """

    kind: Literal["MetricOptimizationKind"] = "MetricOptimizationKind"
    metric: str
    direction: Literal["higher_is_better", "lower_is_better"]
    baseline: float | None = None
    evaluate: str | None = None
    """Shell command that produces the metric value. Must be read-only."""
    evaluate_extract: str = "wall_clock"
    """How to extract the scalar from evaluate's output.

    Values:
        wall_clock        — measure wall-clock time of the evaluate command itself
        regex:<pattern>   — match first capture group against stdout, parse as float
        json:<key>        — parse stdout as JSON, extract named key as float
    """
    correctness: str | None = None
    """Shell command that must exit 0 after every accepted hypothesis.

    The reward-hacking guard: a hypothesis that improves the metric but
    breaks correctness is rejected and reverted. None = no correctness gate.
    """
    target_files: list[str] = Field(default_factory=list)


class TaskExecutionSpec(LoopSpec):
    """Execute a plan with per-task verification.

    Terminal: all tasks pass.
    """

    kind: Literal["TaskExecutionKind"] = "TaskExecutionKind"
    plan_path: str | None = None
    """Path to the plan markdown file the executor works from.

    Relative paths are resolved from the directory containing the spec file.
    The plan file contains a list of tasks with acceptance criteria.
    """
    target_files: list[str] = Field(default_factory=list)


class ConsensusSpec(LoopSpec):
    """Multi-role deliberation toward agreement.

    Terminal: all roles APPROVE (including DRI).
    """

    kind: Literal["ConsensusKind"] = "ConsensusKind"


class InformationSeekingSpec(LoopSpec):
    """Research until a sufficiency threshold is reached.

    Terminal: gap check passes (no material unknowns remaining).
    """

    kind: Literal["InformationSeekingKind"] = "InformationSeekingKind"


class ClarificationSpec(LoopSpec):
    """Elicit requirements from a human.

    Terminal: human explicitly confirms complete.
    HUMAN_GATED: True — cannot be auto-terminated by the executor.
    """

    kind: Literal["ClarificationKind"] = "ClarificationKind"
    HUMAN_GATED: ClassVar[bool] = True


class SelectionSpec(LoopSpec):
    """Rank and select among candidates.

    Terminal: best candidate identified with sufficient confidence.
    """

    kind: Literal["SelectionKind"] = "SelectionKind"


# ---------------------------------------------------------------------------
# Registry and loader
# ---------------------------------------------------------------------------


_KIND_MAP: dict[str, type[LoopSpec]] = {
    "MetricOptimizationKind": MetricOptimizationSpec,
    "TaskExecutionKind": TaskExecutionSpec,
    "ConsensusKind": ConsensusSpec,
    "InformationSeekingKind": InformationSeekingSpec,
    "ClarificationKind": ClarificationSpec,
    "SelectionKind": SelectionSpec,
}


def load_spec(path: str | Path) -> LoopSpec:
    """Load and validate a loop spec from a YAML file.

    Raises:
        FileNotFoundError: if the path does not exist
        ValueError: if kind is missing or unknown
        pydantic.ValidationError: if required fields are missing or invalid
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Spec not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Spec must be a YAML mapping, got {type(data).__name__}")
    kind = data.get("kind")
    if kind not in _KIND_MAP:
        raise ValueError(
            f"Unknown loop kind: {kind!r}. "
            f"Valid kinds: {sorted(_KIND_MAP)}"
        )
    return _KIND_MAP[kind].model_validate(data)


__all__ = [
    "ExecutorSpec",
    "TurnResult",
    "LoopSpec",
    "TerminalConditions",
    "MetricOptimizationSpec",
    "TaskExecutionSpec",
    "ConsensusSpec",
    "InformationSeekingSpec",
    "ClarificationSpec",
    "SelectionSpec",
    "load_spec",
]
