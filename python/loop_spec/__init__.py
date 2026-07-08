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

from pathlib import Path
from typing import ClassVar, Literal

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ExecutorSpec — how the agent is invoked (closes the "handoff is a file" gap)
# ---------------------------------------------------------------------------


class ExecutorSpec(BaseModel):
    """Declares how the agent executor is invoked for each turn.

    Executors are external processes — they do not import the loop-spec SDK.
    The execution fabric (e.g. Saturate) launches them, monitors them, and
    recovers from crashes.

    Types:
        hermes  — Hermes agent profile (requires ``profile``)
        shell   — arbitrary executable with LOOP_* env vars (requires ``command``)
        http    — POST TurnContext JSON, receive TurnResult JSON (requires ``url``)
    """

    type: Literal["hermes", "shell", "http"] = "shell"
    profile: str | None = None  # hermes: agent profile name
    command: str | None = None  # shell: executable + args
    url: str | None = None  # http: POST endpoint


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

    kind: str
    name: str
    level: Literal["L1", "L2", "L3"] = "L1"
    terminal: TerminalConditions = Field(default_factory=TerminalConditions)
    executor: ExecutorSpec = Field(
        default_factory=lambda: ExecutorSpec(type="shell", command="echo no-executor")
    )
    memory: str = "./output"
    """Output directory for findings, committed hypotheses, and completion reports."""


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
