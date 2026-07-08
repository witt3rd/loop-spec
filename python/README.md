# loop-spec-py

Python implementation of the [loop-spec](https://github.com/witt3rd/loop-spec)
specification. Provides Pydantic v2 models for all six loop kinds and a
`load_spec()` function for validating YAML spec files.

## Install

```bash
pip install loop-spec-py
```

## Usage

```python
from loop_spec import load_spec, MetricOptimizationSpec

spec = load_spec("path/to/spec.yaml")
assert isinstance(spec, MetricOptimizationSpec)
print(spec.metric, spec.direction, spec.baseline)
```

## Loop kinds

`MetricOptimizationKind`, `TaskExecutionKind`, `ConsensusKind`,
`InformationSeekingKind`, `ClarificationKind`, `SelectionKind`

See the [specification](../schema/loop-spec.json) for the full schema.
