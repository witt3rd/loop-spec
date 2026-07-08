"""Tests for loop_spec Python implementation."""
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from loop_spec import (
    ClarificationSpec,
    MetricOptimizationSpec,
    SelectionSpec,
    TaskExecutionSpec,
    load_spec,
)


def write_spec(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


class TestLoadSpec:
    def test_metric_optimization(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "test-loop",
            "metric": "score",
            "direction": "higher_is_better",
        })
        spec = load_spec(p)
        assert isinstance(spec, MetricOptimizationSpec)
        assert spec.level == "L1"
        assert spec.terminal.max_iterations == 100

    def test_task_execution(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "my-plan",
        })
        spec = load_spec(p)
        assert isinstance(spec, TaskExecutionSpec)

    def test_selection_kind(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "SelectionKind",
            "name": "pick-best",
        })
        spec = load_spec(p)
        assert isinstance(spec, SelectionSpec)

    def test_missing_required_field_raises(self, tmp_path):
        # MetricOptimizationKind requires metric and direction
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "bad-spec",
            # missing metric and direction
        })
        with pytest.raises(ValidationError):
            load_spec(p)

    def test_unknown_kind_raises(self, tmp_path):
        p = write_spec(tmp_path, {"kind": "BogusKind", "name": "x"})
        with pytest.raises(ValueError, match="Unknown loop kind"):
            load_spec(p)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_spec(tmp_path / "nonexistent.yaml")

    def test_malformed_yaml_raises(self, tmp_path):
        p = tmp_path / "spec.yaml"
        p.write_text("key: [unclosed", encoding="utf-8")
        with pytest.raises(Exception):
            load_spec(p)

    def test_clarification_is_human_gated(self):
        assert ClarificationSpec.HUMAN_GATED is True

    def test_defaults(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "defaults-test",
        })
        spec = load_spec(p)
        assert spec.level == "L1"
        assert spec.terminal.max_iterations == 100
        assert spec.terminal.plateau_count == 10
        assert spec.terminal.target_score is None

    def test_all_six_kinds_load(self, tmp_path):
        kinds = [
            ("MetricOptimizationKind", {"metric": "s", "direction": "higher_is_better"}),
            ("TaskExecutionKind", {}),
            ("ConsensusKind", {}),
            ("InformationSeekingKind", {}),
            ("ClarificationKind", {}),
            ("SelectionKind", {}),
        ]
        for kind, extra in kinds:
            p = tmp_path / f"{kind}.yaml"
            p.write_text(yaml.dump({"kind": kind, "name": "t", **extra}), encoding="utf-8")
            spec = load_spec(p)
            assert spec.kind == kind
