# loop-spec

**The open specification for loop-shaped agentic work.**

`loop-spec` defines the canonical taxonomy and contract for expressing,
validating, and exchanging loop-shaped AI agent tasks — independent of any
particular execution framework, language, or runtime.

It is to agentic loop engineering what OpenAPI is to HTTP APIs: a
language-agnostic specification with implementations in whatever runtimes
you need.

---

## The Problem

Every agentic loop framework invents its own schema for expressing what a
loop *is* — what kind it is, what done looks like, how long it can run, what
level of autonomy it has. These schemas are incompatible. A loop designed for
one framework cannot be validated, scheduled, or monitored by another.

## The Solution

A single, versioned specification for loop-shaped work, with:

- **A canonical loop kind taxonomy** — six kinds covering the full space of
  agentic iteration patterns
- **A typed schema** — required fields per kind, terminal conditions,
  maturity levels
- **A language-agnostic definition** — JSON Schema as the ground truth,
  reference implementations in Python, Rust, TypeScript

Execution frameworks (Saturate, Cyclus, Hermes, etc.) implement the spec.
Loop designers express their intent once. Tools can validate, schedule, and
monitor loops without knowing which framework will run them.

---

## Loop Kind Taxonomy

| Kind | Description | Terminal condition |
|------|-------------|-------------------|
| `MetricOptimizationKind` | Improve a numeric score over iterations | Score exceeds target OR plateau detected |
| `TaskExecutionKind` | Execute a plan with per-task verification | All tasks pass |
| `ConsensusKind` | Multi-role deliberation toward agreement | All roles APPROVE |
| `InformationSeekingKind` | Research until sufficiency threshold | Gap check passes |
| `ClarificationKind` | Elicit requirements from a human | Human confirms complete |
| `SelectionKind` | Rank and select among candidates | Best candidate identified |

## Maturity Levels (L1/L2/L3)

| Level | What the executor may do |
|-------|--------------------------|
| L1 | Observe and propose — read-only, writes only to STATE output |
| L2 | Propose and apply — writes to target files after human confirmation |
| L3 | Autonomous — applies changes without human confirmation |

**All loops start at L1.** Trust is earned through demonstrated L1 behavior
before graduating to L2 or L3.

---

## Spec Format

Loop specs are YAML files:

```yaml
kind: MetricOptimizationKind
name: function-minimization
level: L1

terminal:
  target_score: 1.3
  max_iterations: 100
  plateau_count: 10

# MetricOptimizationKind-specific fields
metric: combined_score
direction: higher_is_better
baseline: 1.42
evaluate: |
  cd examples/function_minimization && python3 code/evaluator.py
target_files:
  - examples/function_minimization/code/initial_program.py
```

Full JSON Schema: [`schema/loop-spec.json`](schema/loop-spec.json)

---

## Implementations

| Language | Package | Status |
|----------|---------|--------|
| Python | `loop-spec-py` | ✅ `loop_spec` in [`python/`](python/) |
| Rust | `loop-spec-rs` | 🔲 planned |
| TypeScript | `loop-spec-ts` | 🔲 planned |
| Protobuf | `.proto` | 🔲 planned |

---

## Used By

- **[Cyclus](https://github.com/witt3rd/hermes-cyclus)** — Hermes-native loop
  orchestration; uses `loop_spec.load_spec()` as the planning gate
- **[Saturate](https://github.com/witt3rd/saturate)** — distributed loop
  execution fabric; uses the spec for task scheduling and budget enforcement

---

## Contributing

The specification lives in `schema/loop-spec.json`. Language implementations
live in subdirectories. To add a new implementation: create
`<language>/README.md` and implement against the JSON Schema.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

MIT. See [LICENSE](LICENSE).
