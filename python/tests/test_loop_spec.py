"""Tests for loop_spec Python implementation."""
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from loop_spec import (
    ClarificationSpec,
    ExecutorSpec,
    InformationSeekingSpec,
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


class TestExecutorSpec:
    def test_default_executor_is_none(self, tmp_path):
        p = write_spec(tmp_path, {"kind": "TaskExecutionKind", "name": "t"})
        spec = load_spec(p)
        assert spec.executor is None

    def test_hermes_executor(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "t",
            "executor": {"type": "hermes", "profile": "forge"},
        })
        spec = load_spec(p)
        assert spec.executor is not None
        assert spec.executor.type == "hermes"
        assert spec.executor.profile == "forge"

    def test_shell_executor(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "s",
            "direction": "lower_is_better",
            "executor": {"type": "shell", "command": "./run.sh"},
        })
        spec = load_spec(p)
        assert spec.executor is not None
        assert spec.executor.type == "shell"
        assert spec.executor.command == "./run.sh"

    def test_http_executor(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "ConsensusKind",
            "name": "t",
            "executor": {"type": "http", "url": "http://localhost:9000/turn"},
        })
        spec = load_spec(p)
        assert spec.executor is not None
        assert spec.executor.type == "http"
        assert spec.executor.url == "http://localhost:9000/turn"

    def test_executor_spec_standalone(self):
        e = ExecutorSpec(type="hermes", profile="my-agent")
        assert e.type == "hermes"
        assert e.profile == "my-agent"


class TestOutputDir:
    def test_output_dir_default(self, tmp_path):
        p = write_spec(tmp_path, {"kind": "TaskExecutionKind", "name": "t"})
        spec = load_spec(p)
        assert spec.output_dir == "./output"

    def test_output_dir_custom(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "t",
            "output_dir": "./output/my-loop",
        })
        spec = load_spec(p)
        assert spec.output_dir == "./output/my-loop"

    def test_no_memory_field(self, tmp_path):
        """memory was renamed to output_dir — old name should not be accepted."""
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "t",
            "memory": "./some/path",  # old field name
        })
        spec = load_spec(p)
        # Pydantic ignores extra fields by default — output_dir stays default
        assert spec.output_dir == "./output"


class TestMetricOptimizationExtensions:
    def test_evaluate_extract_default(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "build_time",
            "direction": "lower_is_better",
        })
        spec = load_spec(p)
        assert isinstance(spec, MetricOptimizationSpec)
        assert spec.evaluate_extract == "wall_clock"

    def test_evaluate_extract_regex(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "score",
            "direction": "higher_is_better",
            "evaluate_extract": r"regex:(\d+\.\d+)",
        })
        spec = load_spec(p)
        assert spec.evaluate_extract == r"regex:(\d+\.\d+)"

    def test_correctness_default_none(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "s",
            "direction": "lower_is_better",
        })
        spec = load_spec(p)
        assert spec.correctness is None

    def test_correctness_set(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "build_time",
            "direction": "lower_is_better",
            "correctness": "npm test",
        })
        spec = load_spec(p)
        assert spec.correctness == "npm test"

    def test_direction_lower_is_better(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "MetricOptimizationKind",
            "name": "t",
            "metric": "latency",
            "direction": "lower_is_better",
        })
        spec = load_spec(p)
        assert spec.direction == "lower_is_better"


class TestTaskExecutionExtensions:
    def test_plan_path_default_none(self, tmp_path):
        p = write_spec(tmp_path, {"kind": "TaskExecutionKind", "name": "t"})
        spec = load_spec(p)
        assert isinstance(spec, TaskExecutionSpec)
        assert spec.plan_path is None

    def test_plan_path_set(self, tmp_path):
        p = write_spec(tmp_path, {
            "kind": "TaskExecutionKind",
            "name": "t",
            "plan_path": "./plans/phase1.md",
        })
        spec = load_spec(p)
        assert spec.plan_path == "./plans/phase1.md"
