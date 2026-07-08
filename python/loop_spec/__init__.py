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


# ---------------------------------------------------------------------------
# Six loop kinds
# ---------------------------------------------------------------------------


class MetricOptimizationSpec(LoopSpec):
    """Improve a numeric metric over iterations.

    Terminal: score exceeds target_score OR plateau_count consecutive
    iterations with no improvement.
    """
    kind: Literal["MetricOptimizationKind"] = "MetricOptimizationKind"
    metric: str
    direction: Literal["higher_is_better", "lower_is_better"]
    baseline: float | None = None
    evaluate: str | None = None  # shell command, must be read-only
    target_files: list[str] = Field(default_factory=list)


class TaskExecutionSpec(LoopSpec):
    """Execute a plan with per-task verification.

    Terminal: all tasks pass.
    """
    kind: Literal["TaskExecutionKind"] = "TaskExecutionKind"
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
