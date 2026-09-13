# Observability Agent Protocol

This document defines how an AI agent must execute the Reed observability build (Issue #7).

It is an operational protocol for the implementing agent. It does not introduce new
architecture. The agent must use `docs/observability_design.md` and the documents it
governs as the source of truth.

## Observability Navigation Map

Do not load every observability document indiscriminately. Use this document as the
operational entry point and load only the context required by the current slice.

```text
observability_agent_protocol.md
        │
        ├── What is the current state?
        │       └── observability_harness.md ("Current slice" section)
        │
        ├── What are the global implementation rules?
        │       └── observability_refactor_guide.md
        │
        ├── What must always remain true?
        │       └── observability_invariants.md
        │
        ├── What must NOT be built?
        │       └── observability_non_goals.md
        │
        ├── What should be implemented next, in what order?
        │       └── observability_harness.md (Milestones and Slices)
        │
        ├── What is the target public API and mechanics?
        │       └── observability_goals.md
        │
        └── Why does the API/mechanics look like this — full reasoning?
                └── observability_design.md (read the specific section the
                    slice touches, not the whole document end to end)
```

## Context Loading Rule

Always read:

1. `observability_agent_protocol.md` (this document);
2. `observability_harness.md`'s current-slice section;
3. `observability_refactor_guide.md`;
4. `observability_invariants.md`;
5. `observability_non_goals.md`;
6. `observability_goals.md`.

Then read only the specific section(s) of `observability_design.md` that the
Slice-To-Documentation Map below points to for the current slice. Do not read
`observability_design.md` end to end for every slice — it is a design *record* (five
rounds of revision, including corrections of earlier rounds), not a spec to re-derive the
current answer from scratch each time. `observability_goals.md`/`observability_non_goals.md`
already distill the current answer; go back to `observability_design.md` for *why*, not to
find *what*.

```text
minimum sufficient context
not
maximum available context
```

## Slice-To-Documentation Map

A router, not a summary. Read the cell's target for the actual rule.

| Concept | Primary source | Design-record section (why) | Non-goal to watch |
|---|---|---|---|
| `execution_id`/`flow_id`/`node_id`/`node_execution_id` | `observability_goals.md` §3 | design §5, §16.3, §17.1 (unresolved stability) | non-goals §10 |
| `Instrument` declaration / `flow.add(instruments=...)` | `observability_goals.md` §2.1-2.2 | design §16.2 | non-goals §2 |
| `ctx.record()` | `observability_goals.md` §2.3 | design §6, §11.2-11.3, §16.2 | non-goals §2, §3, §6 |
| Node identity vs. display name | `observability_goals.md` §2.4 | design §16.5 (retracts §12.3) | non-goals §8 |
| Durability boundary | `observability_goals.md` §5 | design §13.2 (round 4 correction) | non-goals §5 |
| `recordings.csv`/`provenance.csv`/`manifest.json` layout | `observability_goals.md` §6 | design §8 (round 4), §16.4 | non-goals §7 |
| Cross-Execution querying | `observability_goals.md` §7 | design §16.4, §17.2 (Flow-shape drift) | non-goals §7 |
| Provenance `generated`/`used` events | `observability_goals.md` §6 | design §8 (round 4, normalized event log) | -- |
| Execution Trace / terminal renderer (Level 1) | `observability_goals.md` §4 | design §4, §11.1, §8 | non-goals §9 |
| OTel/exporter mapping | `observability_goals.md` §8 | design §9, §16.2 (`kind` gating) | non-goals §4 |

## Blast-Radius Control

Every slice plan (template below) must declare its expected change surface before
production code is touched. After implementation, compare the actual `git diff` against
that declaration.

```text
unexpected change != automatically wrong
unexpected change -> requires explanation before proceeding
```

A materially larger-than-expected diff must be explained and reviewed before another slice
begins.

## Core Rule

The agent must be investigative before being constructive.

```text
read -> inspect -> research -> plan -> implement -> verify -> report
```

Work in small slices. One slice means one coherent step (one row of
`observability_harness.md`'s milestone tables) with a clear definition of done.

## Required Reading Before Any Production Change

1. `docs/observability_harness.md` (current-slice section);
2. `docs/observability_refactor_guide.md`;
3. `docs/observability_invariants.md`;
4. `docs/observability_non_goals.md`;
5. `docs/observability_goals.md`;
6. the specific `observability_design.md` section(s) the Slice-To-Documentation Map names
   for the current slice.

The agent must not rely on memory alone.

## Required Inspection Before Any Production Change

Before implementing any slice, inspect:

1. the affected production files;
2. any existing regression tests protecting current `Run`/`FlowNode`/`NodeContext`/
   `ArtifactRepository` behavior that the slice touches;
3. any existing target/contract tests for the observability surface being built;
4. the current `git status` and branch;
5. `observability_harness.md`'s recorded current slice and completed-slices log.

Explicitly identify: which current behavior must remain valid; which target behavior
should become implemented; which files are in scope; which are out of scope.

## External Research Rule

Not mandatory for every slice. Perform it when:

1. implementation depends on a Python/filesystem/CSV mechanism whose semantics need
   confirmation (e.g. atomic append behavior, `fsync` guarantees on the target platform);
2. the design record explicitly references an external pattern relevant to the slice
   (OTel SDK internals, DuckDB glob semantics, PROV/ProvONE);
3. the current implementation exposes a technical uncertainty (e.g. how `flow_id`
   stability should actually be derived — Section 2 of `observability_refactor_guide.md`);
4. implementation alternatives have materially different correctness consequences.

Do not perform external research to search for "a better architecture." The architecture
is decided (rounds 1-5 of `observability_design.md`) except for the two explicitly flagged
open items. Research clarifies implementation mechanics or resolves a flagged open item; it
does not reopen settled design.

## Slice Plan Requirement

Write a slice plan before modifying production code:

```markdown
## Slice Plan

### Slice name

### Milestone / row in observability_harness.md

### observability_design.md section(s) this slice implements

### Current implementation inspected

### Regression tests protecting current behavior

### Target tests expected to move (or to be written)

### External references checked

### Scope

### Non-scope

### Expected Change Surface

Production files expected to change:

Test files expected to change:

Documentation expected to change:

Files explicitly outside the expected change surface:

### Risks

### Definition of done

### Implementation steps
```

If the plan reveals the slice is too large, split it before editing production code.

## Slice Scope Rule

Implement only the current slice. Do not combine independent pieces of observability work
in one slice. Examples of separate slices, drawn from `observability_harness.md`'s
milestones:

1. identity fields on `Run`/`FlowNode`/`NodeRuntime` (O1);
2. `NodeContext`'s identity-bundle addition (O1);
3. resolving `flow_id`/`node_id` cross-run stability (O1 — must precede everything that
   depends on it);
4. `Instrument` class + `flow.add(instruments=...)` (O2);
5. `ctx.record()` + lazy-mode conflict detection (O2);
6. resolving `kind="event"`'s fate (O2 — must precede any non-metric recording work);
7. `RecordingStore`/CSV writer + `manifest.json` (O3);
8. durability-boundary flush wiring in `NodeRuntime` (O3);
9. provenance event emission (O4);
10. Execution Trace ring buffer + terminal renderer (O5);
11. OTel exporter adapter / `reed describe`/`query`/`graph` tooling (O6).

If a change is useful but outside the slice, report it as future work. Do not implement it
opportunistically.

## Non-Goals Enforcement

Follow `docs/observability_non_goals.md`. In particular, do not:

1. implement `Recording`/`Instrument` against the literal OTel Metrics SDK data types;
2. add `Histogram` to `Instrument.kind` without a concrete use case;
3. add `ctx.metrics`/`ctx.otel`/`ctx.grafana`;
4. accept non-scalar `value` or auto-flatten arrays;
5. infer OTel export mapping from `type(value)`;
6. describe the local record as "never lossy" or add an `fsync` per `ctx.record()` call;
7. inject exceptions/cancellations into `ctx.record()` via a reserved name;
8. partition physical storage per Node or per Instrument, or share a recordings file
   across Executions;
9. add a Node-name-uniqueness validation or a `name=` parameter to `flow.add(...)`;
10. revive any Bus/Depot/Outpost tracing machinery;
11. silently pick a default for `kind="event"` or for `flow_id`/`node_id` stability instead
    of resolving them explicitly.

## Test Discipline

Same regime as Reed's architectural refactor: identify, before changing production code,
either (1) the regression test protecting preserved behavior, (2) the target/contract test
that should move from failure to passing, or (3) the missing test that must be added first.
Do not weaken assertions, convert `xfail(strict=True)` to a weaker skip, or delete a test to
get a green suite.

## Stop Conditions

Stop and report when:

1. a slice would require resolving `flow_id`/`node_id` stability or `kind="event"`'s fate
   as an unplanned side effect, rather than as its own dedicated slice;
2. `observability_design.md` and `observability_goals.md`/`observability_non_goals.md`
   disagree;
3. ownership between `Run`, `FlowNode`, `NodeRuntime`, `NodeExecution`, and the new
   identity/recording objects is unclear;
4. a required change significantly expands scope beyond the current slice's category;
5. the durability-boundary flush point interacts with `NodeRuntime`'s existing
   exception/cancellation handling in a way the design record does not specify;
6. checks fail for a reason that cannot be explained.

Stopping is preferable to inventing architecture or quietly resolving a flagged open item.

## Reporting Requirement

After every slice, report: what changed; which `observability_design.md` section(s) were
implemented; which files changed; which tests ran and passed; which target tests moved
from expected failure to passing; whether `observability_harness.md`'s current-slice
section was updated; any ambiguity or future work.

## Observability-State Update

After a slice, update `docs/observability_harness.md`'s current-slice/completed-slices
record when: a slice completes; a new open question is discovered; one of the two flagged
open items (Section 2 of `observability_refactor_guide.md`) is resolved; a known
architectural question is resolved or newly discovered. Do not leave it stale after
meaningful progress — it is the operational checkpoint for the next agent, exactly as
`refactor_state.md` was for Reed's prior architectural refactor.

## Agent Mindset

```text
understand first
plan narrowly
change carefully
verify completely
report honestly
```

## One-Slice Termination Rule

Completing one slice does not authorize starting the next slice. After verification, state
update, and reporting, stop. The next slice requires a new explicit task or instruction.
