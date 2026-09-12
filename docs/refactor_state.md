# Refactor State

This document tracks the current execution state of the Reed architectural refactor.

It is a live operational checkpoint, not an architectural decision document.

Related documents:

1. `architectural_decision.md`;
2. `parcel_boundary_decision.md`;
3. `node_context_decision.md`;
4. `flow_composition_implementation_basis.md`;
5. `implementation_refactor_assessment.md`;
6. `refactor_priority_order.md`;
7. `refactor_guide.md`;
8. `refactor_agent_protocol.md`;
9. `non-goals.md`;
10. `architectural_invariants.md`.

## Workspace State

- Branch: `4-replace-flow-with-an-explicit-flow-composition-api`
- Last known base commit: `4fb0a76` ("Milestone 1 concluded.") -- Milestone 1 (Slices 1A-1F) is committed and is the validated baseline for Milestone 2. The prior `54f20ce87be8574a1bb6df1973797b1e91887aa9` baseline and the long uncommitted Slice 1A-1F file list this section used to carry are superseded; see the Slice 1A-1F records and Completed Slices rows below for what that commit contains.
- Working tree: dirty (Slice 2A's changes, uncommitted)
- Production code modified: yes -- Slice 2A added one new file (`src/reed/execution/run.py`) and made small, additive modifications to two committed Milestone-1 files (`src/reed/composition/flow/flow_composition.py`: new `run()` method plus docstring updates; `src/reed/__init__.py`: one new export line) -- see "Slice 2A record" below for the exact list.
- Documentation modified: yes (this file)
- Tests modified: no existing test file changed; one new focused test file added

Current uncommitted work:

- `docs/refactor_state.md` (this update)
- `tests/test_slice_2a_flow_run.py` (new -- Slice 2A)
- `src/reed/execution/run.py` (new -- Slice 2A)
- `src/reed/composition/flow/flow_composition.py` (modified -- Slice 2A: adds `run()`; docstring updates)
- `src/reed/__init__.py` (modified -- Slice 2A: exports `Run`)
- `AGENTS.md` (repo root, pre-existing untracked, unrelated to this refactor)
- `CLAUDE.md` (repo root, pre-existing untracked, unrelated to this refactor)

## Baseline Verification

Last verified: 2026-09-12

Configured command:

```bash
uv run pytest -q
```

Result (as of 2026-09-12, after Slice 2A):

```text
83 passed, 6 xfailed
```

Coverage percentage not re-measured this session (sandbox could not write
`.coverage` in the mounted working tree); this does not affect pass/fail
counts. Breakdown: 24 pre-existing regression tests (unchanged) + 10
Slice 1A focused tests + 7 Slice 1B focused tests + 7 Slice 1C focused
tests + 8 Slice 1D focused tests + 9 Slice 1E focused tests + 9
Milestone-1 target architecture contract tests (Slice 1F) + 9 Slice 2A
focused tests (`tests/test_slice_2a_flow_run.py`) = 83 passed; the
same 6 Milestone-2 target architecture contract tests stay xfail --
none moved this slice, which matches
`docs/refactor_priority_order.md`'s own prediction for Slice 2A ("No
target test moves alone") (see "Slice-focused test commands" below).

Development dependencies command:

```bash
uv sync --extra dev
```

Result:

```text
pytest, pytest-cov, coverage, and ruff installed successfully
```

Regression test command:

```bash
uv run pytest -q -o addopts='' \
    tests/test_package.py \
    tests/test_current_regression_node_description.py \
    tests/test_current_regression_flow_runtime.py \
    tests/test_current_regression_artifacts_repository.py
```

Result:

```text
24 passed
```

Target architecture contract command:

```bash
uv run pytest -q -o addopts='' tests/test_target_architecture_contract.py
```

Result (as of 2026-09-12, after Slice 1F):

```text
9 passed, 6 xfailed
```

The 9 passing tests are exactly the Milestone-1 target contracts (see
"Target Contract Status" below); the 6 remaining `xfail` tests are
Milestone-2 contracts, each now carrying a precise per-test `xfail`
reason naming the Milestone-2 slice it depends on (2E, 2F, or 2G) in
place of the prior module-level blanket marker.

Slice-focused test command (Slice 1A; see refactor_guide.md #11 -- no
target test moves during this slice, so its own behavior is verified by a
dedicated, non-xfail test file):

```bash
uv run pytest -q -o addopts='' tests/test_slice_1a_domain_signature_parsing.py
```

Result:

```text
10 passed
```

Slice-focused test command (Slice 1B; same rationale -- 1B is a
prerequisite slice, no target test can move):

```bash
uv run pytest -q -o addopts='' tests/test_slice_1b_domain_node_description.py
```

Result:

```text
7 passed
```

Slice-focused test command (Slice 1C; same rationale -- nothing can reach
`FlowNode` publicly until Slice 1F):

```bash
uv run pytest -q -o addopts='' tests/test_slice_1c_flow_node.py
```

Result:

```text
7 passed
```

Slice-focused test command (Slice 1D; same rationale -- not wired into
any Flow-composition entry point until Slice 1F):

```bash
uv run pytest -q -o addopts='' tests/test_slice_1d_artifact_dependency_graph.py
```

Result:

```text
8 passed
```

Slice-focused test command (Slice 1E; same rationale -- `TriggerPolicy`
has no consumer reachable publicly until Slice 1F):

```bash
uv run pytest -q -o addopts='' tests/test_slice_1e_trigger_policy.py
```

Result:

```text
9 passed
```

Slice-focused verification (Slice 1F; different rationale from 1A-1E --
this slice's entire job is to make the nine already-existing Milestone-1
target architecture contract tests pass, so no separate
`tests/test_slice_1f_*.py` file was added; the target architecture
contract command above **is** Slice 1F's focused verification):

```bash
uv run pytest -q -o addopts='' tests/test_target_architecture_contract.py
```

Result:

```text
9 passed, 6 xfailed
```

Slice-focused test command (Slice 2A; no target-contract test is
assigned to this slice -- confirmed by reading all six remaining xfail
tests, each of which requires `NodeRuntime`/commit semantics/callback
dispatch/stateful serialization -- so this dedicated file is Slice 2A's
verification, same rationale as 1A-1E):

```bash
uv run pytest -q -o addopts='' tests/test_slice_2a_flow_run.py
```

Result:

```text
9 passed
```

Regression command specific to Slice 2A (docs/refactor_priority_order.md's
Slice 2A row requires this file stay green; it exercises only the old
decorator `@flow` execution path, unrelated to the new `Flow`/`Run`):

```bash
uv run pytest -q -o addopts='' tests/test_current_regression_flow_runtime.py
```

Result:

```text
3 passed
```

Static check command:

```bash
uv run ruff check src tests
```

Result:

```text
All checks passed
```

## Current Slice

No slice is currently in progress.

Milestone 1 (Slices 1A-1F, Typed Composition Foundation) is complete and
committed (`4fb0a76`, "Milestone 1 concluded.") -- the validated baseline
for Milestone 2. Slice 2A (Milestone 2 -- Run And Execution Boundary) is
also now complete as of 2026-09-12: `Flow` / `Run` separation is real --
`Flow.run()` creates a new `Run` per call, `Run` is associated with its
originating `Flow`, and `Flow` stores no Run-specific state. A same-day
Slice 2A follow-up corrected an overly conservative part of that slice:
each `Run` now also owns its own `Depot`-backed repository instance,
exposed as `run.repository`. Slice 2B (Milestone 2 -- `NodeRuntime`
ownership) is also now complete as of 2026-09-12: `Run` owns a distinct
`NodeRuntime` per materialized node, exposed as
`run.node_runtime(node)` -- an ownership/identity boundary only, with
no execution capability yet. Slice 2C (Milestone 2 -- Domain Value <->
`ArtifactRecord` execution boundary) is also now complete as of
2026-09-12: `ArtifactRecord[DomainType]` exists as Reed's internal,
composition-based (not inheritance-based) wrapper around a domain
value, carrying forward `Parcel`'s version/provenance mechanics as
`ArtifactVersion`/`ArtifactProvenance`; `NodeRuntime.unwrap(record)`
provides the one pure read-side step this slice adds. Nothing commits
an `ArtifactRecord` anywhere yet, and `run.repository` (`Depot`) does
not participate -- see "Slice 2C record" below for why, and "Open
Architectural Questions" for the resulting finding. Slice 2D
(Milestone 2 -- NodeContext runtime: `ctx.memory` + `ctx.last_output`)
is also now complete as of 2026-09-12: `NodeRuntime` owns a private,
node-local memory instance (lazily instantiated from the declared
`MemoryType`, memoized per `NodeRuntime`) and a `last_output` slot
(always `None` in this slice -- no commit exists yet), and
`NodeRuntime.context` constructs a `NodeContext` snapshot exposing
both. `NodeContext` still exposes nothing else -- no back-reference to
`NodeRuntime`/`Run`/`Flow`/repository/bus. See "Slice 2A record",
"Slice 2B record", "Slice 2C record", and "Slice 2D record" below
for the corrected/full history. See "Completed Slices" below for
full results. Starting the next slice (2E) requires a new explicit
task -- see "Next Recommended Slice" and the One-Slice Termination
Rule in `refactor_agent_protocol.md`.

### Slice 1A record (for reference)

Name:

```text
NodeDescriptionBuilder / typed signature parsing
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned):

1. parse domain artifact parameters;
2. detect injected `NodeContext`;
3. reject `NodeContext` as an `InputPort`;
4. validate `NodeContext[MemoryType, OutputType]` against the return type;
5. derive artifact descriptors from domain types;
6. introduce the minimal structural `NodeContext[MemoryType, OutputType]`
   representation itself -- a real, importable generic class with no
   runtime behavior (no `ctx.memory`, no `ctx.last_output`, no
   Run/NodeRuntime wiring) -- so the parser has something concrete to
   detect; see `docs/refactor_priority_order.md`'s "1A / 1C dependency"
   note for why this moved here;
7. preserve current valid regression behavior until an explicit compatibility migration supersedes it.

Result (what was actually delivered):

1. `src/reed/composition/node/domain_signature.py` (new) --
   `DomainNodeSignatureParser` / `DomainNodeSignature`: parses a typed
   domain function signature, detects an injected `NodeContext`
   parameter and excludes it from dataflow inputs, validates
   `NodeContext[MemoryType, OutputType]`'s output type against the
   function's return type, and rejects self-flow signatures. This
   parser is additive -- it does not read, modify, or replace
   `NodeDescriptionBuilder`, `NodeDescription`, or `NodeDefinition`.
2. `src/reed/composition/node/node_context.py` (new) -- the minimal
   structural `NodeContext[MemoryType, OutputType]` shell: a real,
   importable, `Generic`-based class with `__slots__ = ()` and no
   runtime behavior. Not yet exposed at the `reed` package's public
   top level (nothing constructs or consumes it until Slice 1F
   wires `Flow.add(...)` and Slice 2D wires `ctx.memory`); it is
   currently importable only from
   `reed.composition.node.node_context`.
3. `tests/test_slice_1a_domain_signature_parsing.py` (new) -- 10 focused
   tests covering: plain domain-typed parsing, `NodeContext` detection
   and exclusion, `NodeContext` output-type mismatch rejection,
   self-flow rejection, multiple-`NodeContext` rejection, the context
   shell's lack of runtime behavior, missing parameter/return
   annotations, async-function rejection, and `*args`/`**kwargs`
   rejection.

Artifact descriptors (goal item 5, `ArtifactDescriptor`, Priority 3) were
deliberately NOT introduced -- that type belongs to Slice 1B. This
parser's own `DomainNodeSignature` result (plain `(name, type)` tuples,
mirroring the existing `ConsumedParameter`/`ExternalParameter` shape) is
the Slice 1A stand-in and is expected to be superseded once `1B` exists.

Definition of done -- verified:

1. the focused test(s) pass without weakening any assertion (10/10 passed);
2. current regression tests still pass (`uv run pytest -q -o addopts=''` -- 34 passed, 15 xfailed; the pre-existing 24 are unchanged);
3. no production behavior outside signature parsing and the new `NodeContext` shell changed -- confirmed via `git diff --stat`: only two new files under `src/`, zero modified existing production files;
4. no undocumented architectural decision was introduced;
5. no ambiguity was discovered.

### Slice 1B record (for reference)

Name:

```text
ArtifactDescriptor + domain-typed NodeDescription/NodeDefinition
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Priorities 2-3):

1. create `ArtifactDescriptor` (`domain_type`, `role`, `name`), distinguishing consumed (input) from produced (output) descriptors;
2. avoid exposing internal `ArtifactRecord` concepts through `ArtifactDescriptor`;
3. introduce a domain-typed `NodeDescription` that stores domain artifact input descriptors, a domain artifact output descriptor, and an optional `NodeContext` descriptor;
4. introduce a domain-typed `NodeDefinition` that is a reusable typed callable definition owning no flow-local policy, no callback, and no execution state;
5. preserve current valid regression behavior (same `tests/test_current_regression_node_description.py` file as Slice 1A).

Result (what was actually delivered):

1. `src/reed/composition/node/artifact_descriptor.py` (new) --
   `ArtifactRole` (`CONSUMED`/`PRODUCED`) and `ArtifactDescriptor`
   (`domain_type`, `role`, `name`). Identity-only: no value, version, or
   provenance field, so it cannot be mistaken for `ArtifactRecord`
   (Priority 6, Milestone 2).
2. `src/reed/composition/node/domain_node_description.py` (new) --
   `NodeContextDescriptor` (`parameter_name`, `memory_type`,
   `output_type`), `DomainNodeDescription` (`function`,
   `consumed_artifacts`, `produced_artifact`, `context`),
   `DomainNodeDefinition` (wraps a `DomainNodeDescription`; exposes
   `function`/`name`; deliberately has no `propagation_policy` /
   `trigger_policy` / `on_output` field -- that ownership belongs to
   `FlowNode`, Slice 1C/1E), and `DomainNodeDescriptionBuilder`, which
   reuses Slice 1A's `DomainNodeSignatureParser` for all validation
   (self-flow, `NodeContext` output-type matching, missing annotations,
   async/varargs rejection) rather than duplicating it.
3. `tests/test_slice_1b_domain_node_description.py` (new) -- 7 focused
   tests covering: plain domain node descriptor shape, a node with no
   consumed parameters, `NodeContext` exclusion/descriptor population,
   `DomainNodeDefinition`'s absence of flow-local-policy attributes, that
   the builder still enforces Slice 1A's self-flow and `NodeContext`
   output-type validation (proving the reuse is wired correctly, not
   re-testing 1A exhaustively), and that `ArtifactDescriptor` exposes
   only `domain_type`/`role`/`name` (no `ArtifactRecord`-shaped fields).

`NodeKind` (INPUT/TRANSFORM/OUTPUT) was deliberately not carried into the
domain-typed model: the target architecture
(`docs/parcel_boundary_decision.md`) treats every node uniformly as
consuming/producing domain artifact types, with topology and role
inferred from the type graph rather than a declared node kind. This is a
scope decision, not a gap, and is documented in the module docstring.

Definition of done -- verified:

1. focused tests pass without weakening any assertion (7/7 passed);
2. current regression tests still pass (`uv run pytest -q -o addopts=''` -- 41 passed, 15 xfailed; the pre-existing 24 are unchanged);
3. no production behavior outside the new additive files changed -- confirmed via `git diff --stat` restricted to existing tracked `src/` files: empty;
4. no undocumented architectural decision was introduced;
5. no ambiguity was discovered.

### Slice 1C record (for reference)

Name:

```text
FlowNode
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Priority 9):

1. create `FlowNode` as flow-local node participation;
2. store the (domain-typed, Slice 1B) `NodeDefinition`;
3. expose consumed and produced artifact descriptors;
4. store `trigger_policy`, typed against the *existing* `PropagationPolicy` enum (not `TriggerPolicy` -- that rename is Priority 10 / Slice 1E, explicitly not absorbed here);
5. store optional `on_output` with no dispatch semantics yet (dispatch is Milestone 2, Slice 2F);
6. introduce no separate flow-local identity field, no `DependencyRegistry` migration, and no `Flow.add(...)` wiring -- all explicitly deferred to 1D/1E/1F.

Result (what was actually delivered):

1. `src/reed/composition/flow/flow_node.py` (new) -- `FlowNode`, a
   frozen dataclass holding a `DomainNodeDefinition` (Slice 1B),
   `trigger_policy: PropagationPolicy` (default
   `ALL_DEPENDENCIES_CHANGED`), and `on_output: Callable | None`
   (default `None`). `consumed_artifacts`, `produced_artifact`, and
   `context` are properties delegating to
   `definition.description` -- no data is duplicated. No separate
   identity/id field was added: per `docs/non-goals.md`, "Multiple
   Registrations of the Same Node Definition", participation-identity
   semantics are undecided and out of scope; the `FlowNode` instance
   itself is the flow-local reference
   (`docs/architectural_decision.md`, "Flow-Local Node Reference").
   `FlowNode` does not reference `Flow`, register itself anywhere, or
   import anything from `PropagationPolicy`'s eventual `TriggerPolicy`
   replacement -- it depends only on Slice 1B's outputs and the
   existing `propagation_policy.py`.
2. `tests/test_slice_1c_flow_node.py` (new) -- 7 focused tests covering:
   default `trigger_policy`/`on_output`, delegation of
   `consumed_artifacts`/`produced_artifact`/`context` to the wrapped
   definition, presence/absence of the context descriptor, custom
   `trigger_policy`/`on_output` storage, two distinct `FlowNode`
   instances wrapping the same `DomainNodeDefinition` (documenting that
   the object itself is the flow-local reference, with no shared-state
   leakage between them), and that `FlowNode`'s field set is exactly
   `{definition, trigger_policy, on_output}` (pinning that no identity
   field was smuggled in).

Definition of done -- verified:

1. focused tests pass without weakening any assertion (7/7 passed);
2. current regression tests still pass (`uv run pytest -q -o addopts=''` -- 48 passed, 15 xfailed; the pre-existing 24 are unchanged);
3. no production behavior outside the new additive file changed -- confirmed via `git diff --stat` restricted to existing tracked `src/` files: empty;
4. no undocumented architectural decision was introduced;
5. no ambiguity was discovered;
6. `TriggerPolicy` migration (Priority 10) and `DependencyRegistry` migration (Priority 8) were NOT absorbed -- confirmed no reference to a `TriggerPolicy` type or `DependencyRegistry` anywhere in the new file.

### Slice 1D record (for reference)

Name:

```text
DependencyRegistry migrated to FlowNode/artifact-type vocabulary
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Priority 8):

1. preserve unique-producer validation (one producer per domain artifact type);
2. migrate producer/consumer keys from module/`Parcel` to `FlowNode` (Slice 1C) and domain artifact type;
3. add self-flow validation at registration time, as a second, composition-level enforcement of architectural_invariants.md #11;
4. keep the old `Role`/Parcel-keyed `DependencyRegistry` working unmodified, alongside the new registry, rather than replacing it in place;
5. do NOT wire this graph into `Flow.add(...)` (Slice 1F) and do NOT touch `PropagationPolicy`/`TriggerPolicy` (Slice 1E).

Result (what was actually delivered):

1. `src/reed/composition/flow/artifact_dependency_graph.py` (new) --
   `ArtifactDependencyGraph` (Priority 8's own suggested target name),
   `DuplicateArtifactProducerError`, `SelfFlowError`. Keyed by domain
   artifact type; `register(flow_node)` validates self-flow first, then
   uniqueness of producer, then records the producer and adds the
   `FlowNode` to each consumed type's consumer set; `unregister(...)`
   reverses this; `producer_of`/`consumers_of`/`upstream_flow_nodes`/
   `downstream_flow_nodes` provide the structural queries named in
   Priority 8's target shape. Because a `FlowNode` produces exactly one
   domain artifact type (Slice 1B/1C's singular `produced_artifact`),
   this is not a 1:1 mirror of the old multi-type-per-module API -- that
   is a deliberate, documented difference, not an oversight.
2. `src/reed/synchronization/validity/dependency_registry.py` (old
   `DependencyRegistry`) -- confirmed byte-for-byte untouched
   (`git diff --stat` on this path: empty). Its two regression tests
   (`test_dependency_registry_rejects_duplicate_producers_for_same_parcel_type`,
   `test_dependency_registry_exposes_upstream_and_downstream_modules`)
   still pass unmodified.
3. `tests/test_slice_1d_artifact_dependency_graph.py` (new) -- 8 focused
   tests covering: producer/consumer tracking, upstream/downstream
   `FlowNode` queries, duplicate-producer rejection, idempotent
   re-registration of the same `FlowNode`, self-flow rejection for a
   hand-built `FlowNode` that bypasses Slice 1A's parser-level check
   (proving the registry enforces the invariant independently),
   unregister removing producer/consumer entries, distinct output types
   allowing parallel-safe branching (mirroring the target contract's
   `test_parallel_safe_branching_uses_distinct_output_artifact_types` at
   the registry level), and that the old `DependencyRegistry` class is
   confirmed distinct from the new one.

Definition of done -- verified:

1. focused tests pass without weakening any assertion (8/8 passed);
2. current regression tests still pass (`uv run pytest -q -o addopts=''` -- 56 passed, 15 xfailed; the pre-existing 24 are unchanged);
3. no production behavior outside the new additive file changed -- confirmed via `git diff --stat` restricted to existing tracked `src/` files: empty, and the old `dependency_registry.py` specifically confirmed untouched;
4. no undocumented architectural decision was introduced;
5. no ambiguity was discovered;
6. `TriggerPolicy` migration (Priority 10/Slice 1E) and `Flow.add(...)` wiring (Slice 1F) were NOT absorbed -- confirmed no reference to a `TriggerPolicy` type or any `Flow`/`flow.add` usage anywhere in the new file.

### Slice 1E record (for reference)

Name:

```text
PropagationPolicy migrated to TriggerPolicy
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Priority 10):

1. introduce `TriggerPolicy` with the target values `ANY_INPUT_CHANGED`, `ALL_INPUTS_CHANGED`, `MANUAL`;
2. map old `PropagationPolicy` values to new `TriggerPolicy` values;
3. place/relocate the policy's type on `FlowNode` (Slice 1C already owns the field; this slice retypes it);
4. do NOT update execution logic to read from `FlowNode` -- that is deferred to the `Run`/`NodeRuntime` execution boundary (Milestone 2);
5. do NOT touch the old `PropagationPolicy`, `NodeDefinition`, or `Node` (fully regression-protected, unmodified);
6. do NOT begin `Flow.add(...)` (Slice 1F), execution semantics, or callback dispatch.

Result (what was actually delivered):

1. `src/reed/composition/flow/trigger_policy.py` (new) -- `TriggerPolicy`
   enum (`ANY_INPUT_CHANGED`, `ALL_INPUTS_CHANGED`, `MANUAL`) plus
   `from_propagation_policy(...)`, a pure old-to-new value mapping
   (Priority 10 recommended-work item 2). The mapping is not called from
   any execution path -- no compatibility bridge into `Node`'s
   execution-eligibility logic was wired.
2. `src/reed/composition/flow/flow_node.py` (Slice 1C file, modified) --
   `FlowNode.trigger_policy` retyped from `PropagationPolicy` to
   `TriggerPolicy`, default changed from
   `PropagationPolicy.ALL_DEPENDENCIES_CHANGED` to
   `TriggerPolicy.ALL_INPUTS_CHANGED`. This completes the "ownership
   relocated to FlowNode" step docs/refactor_priority_order.md's "FlowNode
   / DependencyRegistry ordering (resolved)" note assigned to 1E; the
   field itself has lived on `FlowNode` since Slice 1C.
3. `src/reed/composition/node/propagation_policy.py`,
   `node_definition.py`, `node.py` -- confirmed byte-for-byte untouched
   (`git diff --stat` on these three paths: empty). The old
   Parcel/decorator-based execution-eligibility logic (`Node`'s `match`
   statement over `PropagationPolicy`) is unmodified and still what
   actually runs today.
4. `tests/test_slice_1c_flow_node.py` (Slice 1C file, modified) -- updated
   to construct/assert `FlowNode.trigger_policy` against `TriggerPolicy`
   instead of `PropagationPolicy`, since the field's type legitimately
   changed in this slice; all 7 tests still pass.
5. `tests/test_slice_1e_trigger_policy.py` (new) -- 9 focused tests
   covering: `TriggerPolicy`'s exact value set, that it is a distinct enum
   from `PropagationPolicy`, `from_propagation_policy(...)` mapping every
   old value correctly (parametrized) and covering every current
   `PropagationPolicy` member without raising, `FlowNode`'s default and
   explicit `trigger_policy` now being `TriggerPolicy` instances, and a
   direct confirmation that the old `PropagationPolicy`/`NodeDefinition`
   default are untouched.

Definition of done -- verified:

1. focused tests pass without weakening any assertion (9/9 passed; Slice 1C's updated 7/7 also still pass);
2. current regression tests still pass (`uv run pytest -q -o addopts=''` -- 65 passed, 15 xfailed; the pre-existing 24 are unchanged);
3. no production behavior outside `flow_node.py` (a Slice 1C target-architecture file, not legacy-protected) and the new `trigger_policy.py` changed -- confirmed via `git diff --stat` restricted to existing tracked `src/` files: empty, and `propagation_policy.py`/`node_definition.py`/`node.py` specifically confirmed untouched;
4. no undocumented architectural decision was introduced -- the `ON_ANY_INPUT_CHANGED` vs. `ANY_INPUT_CHANGED` doc-typo was already resolved and recorded in `docs/reed_refactor_harness.md` prior to this slice, not newly discovered here;
5. no ambiguity was discovered;
6. `TriggerPolicy` -> execution logic wiring, `Flow.add(...)`, and callback dispatch were explicitly not absorbed.

### Slice 1F record (for reference)

Name:

```text
Flow.add(...) -- Milestone 1 integration gate
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Priority 11 remainder; this task's own instruction):

1. connect the composition-layer pieces already introduced in Slices 1A-1E into the target `Flow.add(...)` composition surface (`NodeDefinition -> Flow.add(...) -> FlowNode -> ArtifactDependencyGraph`);
2. `Flow.add(...)` returns a `FlowNode`;
3. `trigger_policy` and `on_output` are keyword-only composition arguments, stored as Flow-local metadata only -- not evaluated or invoked;
4. reject positional callback/policy ambiguity;
5. enforce artifact producer uniqueness and self-flow validation through the composition graph;
6. public composition based on domain types, not internal records;
7. do NOT absorb `Flow.run()`, `Run`, `NodeRuntime`, `NodeExecution`, `ArtifactRecord` wrapping/unwrapping, `NodeMemory`, `ctx.memory`/`ctx.last_output`, callback dispatch (sync or async), commit semantics, stateful-firing serialization, or `ArtifactRepository` migration (all Milestone 2);
8. identify exactly which xfail target tests are expected to move, and update only that xfail scope -- never weaken an assertion.

Result (what was actually delivered):

1. `src/reed/composition/flow/flow_composition.py` (new) -- the target `Flow` class. Owns a list of registered `FlowNode`s and one `ArtifactDependencyGraph` per instance; owns no Run-specific execution state (architectural_invariants.md #4, #6). `add(function, *, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED, on_output=None)` builds a `DomainNodeDefinition` via Slice 1A/1B's parser and builder (where self-flow and `NodeContext` output-type validation happen), wraps it in a `FlowNode` (Slice 1C) carrying `trigger_policy`/`on_output` as inert metadata, registers it against the `ArtifactDependencyGraph` (Slice 1D -- unique-producer/self-flow validation), and returns the `FlowNode`. `trigger_policy`/`on_output` are keyword-only, so `flow.add(fn, callback, policy)` raises `TypeError` rather than being accepted ambiguously. This class deliberately has no `run()` method -- the natural, non-special-cased reason the six Milestone-2 target tests (all of which call `flow.run()`) continue to fail with `AttributeError` and stay `xfail`. This class is unrelated to the old, decorator-bound, regression-protected `reed.composition.flow.flow.Flow` (`Generic[P, R]`), which remains untouched and is never imported by `reed/__init__.py`; the two share a class name in different modules only.
2. `src/reed/flow.py` (new) -- thin top-level module re-exporting `FlowNode`, giving the target API's documented `from reed.flow import FlowNode` shape. Distinct dotted path from the `reed.composition.flow` implementation package; no collision.
3. `src/reed/__init__.py` (modified, additive) -- three lines appended: `from reed.composition.flow.flow_composition import Flow`, `from reed.composition.flow.trigger_policy import TriggerPolicy`, `from reed.composition.node.node_context import NodeContext`. The two pre-existing lines (`Parcel`, `flow`/`node`/`output`/`input`) are untouched.
4. Docstring-only corrections (no behavior change) to four Slice 1A-1E files that had documented themselves as "not yet wired": `src/reed/composition/node/node_context.py`, `src/reed/composition/flow/flow_node.py`, `src/reed/composition/flow/artifact_dependency_graph.py`, `src/reed/composition/flow/trigger_policy.py` -- each now records that `Flow.add(...)` (Slice 1F) is the thing that wires it.
5. A real Milestone-1 gap discovered and fixed during this slice's own verification pass, not part of the original plan: `DomainNodeSignatureParser.__init__` (Slice 1A, `domain_signature.py`) called `typing.get_type_hints(function)` using only `function.__globals__`. Because the target contract tests (and ordinary user code) commonly import `NodeContext` and define a node function inside the same enclosing function/test body -- under `from __future__ import annotations` -- a name imported into that enclosing local scope is invisible to `function.__globals__`, so two of the nine Milestone-1 target tests (`test_node_context_is_injected_and_not_registered_as_input_port`, `test_node_context_output_type_must_match_return_type`) failed with `NameError: name 'NodeContext' is not defined` rather than exercising the intended validation. This is not Milestone-2 runtime behavior and not a test defect (the target contract's local-import style is ordinary, common Python); it is a real composition-time signature-resolution gap in already-delivered Milestone-1 code, so it was fixed rather than reported as a stop-and-report mismatch. Fix: `DomainNodeSignatureParser.__init__` and `DomainNodeDescriptionBuilder.__init__` (`domain_node_description.py`) now accept an optional keyword-only `extra_globalns: dict[str, object] | None = None` (default `None`, preserving the original Slice 1A behavior exactly for any caller that does not pass it); `Flow.add(...)` captures its immediate caller's local namespace and passes it through so annotation resolution no longer depends on where the referenced name was imported. Only the direct caller is inspected -- no multi-level stack walking. **Refined by the Slice 1F follow-up (2026-09-12, maintenance, not a new architectural slice):** `Flow.add(...)` originally captured the caller's frame unconditionally on every call, before it was known whether it was even needed. It now attempts normal resolution first (no `extra_globalns`) and only inspects `sys._getframe(1)` and retries once, with the caller's locals merged in, if that first attempt raises `NameError` -- see `domain_signature.py`'s module docstring for the documented limitation and `flow_composition.py`'s `add()` for the retry logic. Behavior and target-contract results are unchanged (9 passed, 6 xfailed); this narrows the mechanism to a true fallback rather than a default path.
6. `tests/test_target_architecture_contract.py` (modified) -- the module-level blanket `pytestmark = pytest.mark.xfail(...)` removed; per-test `@pytest.mark.xfail(strict=True, reason=...)` decorators added to exactly the six Milestone-2 tests (`test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value`, `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output`, `test_stateful_node_runtime_firings_are_serialized`), each reason citing the specific Milestone-2 slice (2E, 2F, or 2G per `refactor_priority_order.md`'s Milestone 2 table) that test's verification belongs to. No assertion in this file was touched.

Definition of done -- verified:

1. exactly the nine Milestone-1 target tests pass and exactly the six Milestone-2 target tests remain `xfail` (`uv run pytest -q -o addopts='' tests/test_target_architecture_contract.py` -- 9 passed, 6 xfailed, zero XPASS);
2. full suite: 74 passed, 6 xfailed (`uv run pytest -q -o addopts=''`);
3. `uv run ruff check src tests` -- all checks passed;
4. `git diff --stat` on existing tracked files touched exactly `src/reed/__init__.py` (+4/-0) and `tests/test_target_architecture_contract.py` (xfail markers only, no assertion changed); all other Slice 1F changes are new, previously-untracked files;
5. no target test assertion was weakened -- only xfail-scope changed, and only after the corresponding behavior was implemented and verified passing (docs/refactor_guide.md #11);
6. architectural invariants re-confirmed: `Flow` owns no Run-specific execution state and has no `run()` method (#4, #6); `NodeContext != InputPort` (#12) unchanged, `Flow.add(...)` delegates entirely to Slice 1A/1B for that exclusion; unique-producer and self-flow validation happen through `ArtifactDependencyGraph` (#10, #11); `TriggerPolicy`/`on_output` are stored, never evaluated or invoked (#18-20); public composition surface (`Flow`, `FlowNode`, `TriggerPolicy`, `NodeContext`) is domain-typed, no `ArtifactRecord`/runtime type crosses the boundary (#24-26);
7. Milestone-2 scope was not absorbed: no `Flow.run()`, `Run`, `NodeRuntime`, `NodeExecution`, `ArtifactRecord` wrap/unwrap, `NodeMemory`, `ctx.memory`/`ctx.last_output`, callback dispatch, commit semantics, stateful-firing serialization, or `ArtifactRepository` migration exists anywhere in this diff;
8. no target contract required Milestone-2 runtime behavior to pass -- all nine are composition-time only (none call `flow.run()`), confirmed by reading every one of the nine test bodies before implementation; no stop-and-report mismatch applied.

### Slice 2A record (for reference)

Name:

```text
Flow / Run separation -- Flow.run() creates a Run
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Milestone 2 Slice 2A row; docs/architectural_decision.md, "Run"; this task's own instruction):

1. make `Flow != Run` real: `Flow.run()` creates and returns a new `Run` associated with that `Flow`;
2. each call to `Flow.run()` produces a distinct `Run`;
3. `Flow` remains reusable and composition-oriented; Run-specific mutable execution state must not be stored on `Flow`;
4. introduce only the minimal `Run` representation and `Flow.run()` wiring needed for the identity/ownership boundary -- no later Milestone 2 execution machinery (`NodeRuntime`, `ArtifactRecord` wrap/unwrap, `NodeContext` runtime behavior, `ctx.memory`, `ctx.last_output`, `NodeExecution`, transactional firing, commit semantics, `on_output` dispatch, async callbacks, callback failure handling, stateful firing serialization, `ArtifactRepository` migration, advanced scheduling, parallel execution);
5. identify whether any remaining target-contract xfail is assigned to this slice (none is), and do not invent tests to manufacture false progress;
6. if ownership is ambiguous, stop and report rather than choosing a new architecture.

Result (what was actually delivered):

1. `src/reed/execution/run.py` (new, new subpackage `reed.execution`) -- the minimal `Run` class. Holds only a reference back to its originating `Flow` (`.flow` property, `TYPE_CHECKING`-guarded import to avoid a runtime circular import with `flow_composition.py`). Owns no other state; no `NodeRuntime`, no `.repository`, no `.publish(...)`, nothing execution-capable.
2. `src/reed/composition/flow/flow_composition.py` (modified) -- `Flow.run()` added: `return Run(self)`. No new attribute was added to `Flow.__init__`; `Flow` keeps no list, counter, or reference to any `Run` it has created, so it owns no Run-specific state before or after any number of `run()` calls (verified structurally by a focused test that snapshots `vars(flow)` before and after several `run()` calls and asserts identity-equality of every value). Module/class/method docstrings updated to describe the new scope and to remove the now-false "this class deliberately has no `run()` method" claim.
3. `src/reed/__init__.py` (modified, additive) -- one line appended: `from reed.execution.run import Run`.
4. `tests/test_slice_2a_flow_run.py` (new) -- 9 focused tests: `Flow.run()` returns a `Run`; two calls return distinct instances; the returned `Run`'s `.flow` is the originating `Flow`; distinct `Flow`s produce `Run`s associated with their own `Flow` (not cross-wired); `Flow` is reusable across many `run()` calls and `add()` still works after `run()` has been called; `Flow`'s own instance `__dict__` is unchanged (by key set and by value identity) after calling `run()` repeatedly; and two explicit negative tests pinning the deliberate scope boundary -- `Run` has no `.repository`, `.publish`, or `.node_runtime` yet.
5. No target architecture contract test moved -- confirmed in advance by reading all six remaining xfail test bodies (all require `NodeRuntime`/commit semantics/callback dispatch/stateful serialization) and confirmed after implementation (`tests/test_target_architecture_contract.py` unchanged: 9 passed, 6 xfailed, zero XPASS). This matches `docs/refactor_priority_order.md`'s own Slice 2A row ("No target test moves alone") and the task's own explicit acceptance of this outcome.
6. `tests/test_current_regression_flow_runtime.py` (the old decorator `@flow` execution path, docs/refactor_priority_order.md's named regression guard for this slice) reconfirmed green and untouched: 3 passed.
7. **A documented scope conflict was raised and reported (Stop Condition #2, "two documents conflict"), but the resolution reached at the time was incorrect, and was corrected the same day by a Slice 2A follow-up:** `docs/refactor_priority_order.md`'s Slice 2A row says `Run` should get a `.repository` accessor, backed by "whatever the current storage class is called internally (still `Depot`)". This slice originally deferred that accessor, reasoning that `Depot.__init__(self, bus: Bus)` required standing up "the full legacy transportation/lifecycle stack" and that doing so would be a speculative abstraction under `docs/non-goals.md`. A dedicated Pre-2B Review ("Run Repository Ownership", requested before Slice 2B, read-only) found both reasons incorrect on closer inspection: constructing a `Bus` + `Depot` pair (`Bus.create()` then `Depot(bus=bus)`) is the same trivial, already-used, regression-tested two-line pattern `Logistics.__init__` already relies on today -- not heavy legacy machinery -- and `docs/non-goals.md`'s "Repository Exposure" / "Execution Infrastructure Exposure" sections are scoped explicitly to `NodeContext` and the public node-function-body API, not to `Run`'s own accessor. A same-day Slice 2A follow-up corrected the deferral: `Run.__init__` now constructs its own `Bus` + `Depot` pair and exposes it as `run.repository`; `test_run_has_no_repository_accessor_yet` was replaced with positive tests asserting the accessor exists, is `Depot`-backed, and is distinct per `Run`. The "Open Architectural Questions" entry this conflict was originally recorded under has been resolved and removed (see below). See the Refactor State Log for the full corrected history.

Definition of done -- verified:

1. `flow.run()` returns a `Run`; two calls return distinct `Run` instances; the returned `Run` is associated with its originating `Flow`; `Flow` remains reusable across repeated `run()`/`add()` calls; `Flow` acquired no Run-specific mutable state (9/9 focused tests passed, including a structural `vars(flow)` identity check);
2. full suite: 83 passed (74 pre-existing + 9 new Slice 2A focused tests), 6 xfailed (unchanged) -- `uv run pytest -q -o addopts=''`;
3. target architecture contract: 9 passed, 6 xfailed, zero XPASS -- unchanged from before this slice, a valid outcome explicitly anticipated by the task instructions and by `docs/refactor_priority_order.md`;
4. `tests/test_current_regression_flow_runtime.py` (the named regression guard for this slice): 3 passed, unchanged;
5. `uv run ruff check src tests` -- all checks passed;
6. blast radius (now meaningful again, since Milestone 1 is committed): `git diff --stat` shows exactly `src/reed/__init__.py` (+1/-0) and `src/reed/composition/flow/flow_composition.py` (52 insertions, 14 deletions -- docstrings plus the new `run()` method) modified among tracked files; `src/reed/execution/run.py` and `tests/test_slice_2a_flow_run.py` are new, untracked files; nothing else changed;
7. architectural invariants re-confirmed: `Flow != Run` (#4) and `Flow` owns no Run-specific execution state (#6) -- verified structurally, not just by inspection; `NodeDefinition != FlowNode != NodeRuntime != NodeExecution` (#1-3) unaffected, since neither `NodeRuntime` nor `NodeExecution` exists yet; no Public Boundary invariant (#24-26) affected, since `Run` exposes nothing new across that boundary yet;
8. no later Milestone 2 behavior was introduced: no `NodeRuntime`, no `ArtifactRecord` wrap/unwrap, no `NodeContext` runtime behavior, no `ctx.memory`/`ctx.last_output`, no `NodeExecution`, no transactional firing, no commit semantics, no `on_output` dispatch, no callback failure handling, no stateful firing serialization, no `ArtifactRepository` migration, no advanced scheduling, no parallel execution. `Run.repository` exists (added by the same-day Slice 2A follow-up, correcting the deferral originally recorded here) as a plain, `Depot`-backed, per-`Run` accessor only -- nothing reads or writes through it yet, `Depot` is not renamed, and no domain-facing `get`/`set` API is defined on it.

### Slice 2B record (for reference)

Name:

```text
NodeRuntime ownership -- Run.node_runtime(node) materializes one FlowNode per Run
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Milestone 2 Slice 2B row and Priority 13's traceability split "runtime ownership -> 2B"; docs/architectural_decision.md, "Node Runtime"; this task's own instruction):

1. make the next execution boundary real: `FlowNode -> NodeRuntime`, owned by one `Run`;
2. a `NodeRuntime` exists per (`Run`, `FlowNode`) pair, created and held by `Run`;
3. the same node looked up twice on the same `Run` returns the same `NodeRuntime`; two different `Run`s (even from the same `Flow`) never share one;
4. `FlowNode` acquires no Run-specific mutable execution state; `Flow` acquires no `NodeRuntime` ownership;
5. if the accepted architecture specifies how `Run` exposes/indexes its `NodeRuntime`s, follow that design rather than inventing another API;
6. introduce only the minimal representation needed -- no argument construction, unwrapping, `NodeContext` injection, `NodeMemory`, execution, commit, or callback dispatch (all later Milestone 2 slices).

Result (what was actually delivered):

1. `src/reed/execution/node_runtime.py` (new) -- the minimal `NodeRuntime` class. Holds only a reference back to its owning `Run` (`.run` property) and to the `FlowNode` it materializes (`.flow_node` property), both `TYPE_CHECKING`-guarded imports to avoid runtime circularity. Owns no other state: no `NodeMemory`, no `ctx.memory`/`ctx.last_output`, no execution capability, and no reference to `run.repository` (Outpost -> NodeRuntime's eventual "repository communication" responsibility per `docs/flow_composition_implementation_basis.md` is explicitly deferred, not wired here).
2. `src/reed/execution/run.py` (modified) -- `Run.node_runtime(node)` added: resolves `node` (the original callable passed to `Flow.add(...)`) to its `FlowNode` by identity match against `self._flow.flow_nodes`, then get-or-creates and memoizes a `NodeRuntime` in a new `self._node_runtimes: dict[FlowNode, NodeRuntime]` (initialized in `__init__`, empty until first lookup). Raises `ValueError` if `node` was never registered on this `Run`'s `Flow`. The access shape (`run.node_runtime(<original node function>)`) follows `tests/test_target_architecture_contract.py::test_run_instances_isolate_node_memory`'s existing, already-accepted usage (`run.node_runtime(track)`) rather than inventing a new API, per this task's own instruction and Stop Condition #4 ("ownership between Flow, Run, FlowNode, NodeRuntime, or NodeExecution is unclear") -- that ambiguity did not arise because the target-contract test already specifies the shape.
3. `src/reed/composition/flow/flow_composition.py` (modified) -- a new read-only `flow_nodes` property added to `Flow` (`tuple(self._flow_nodes)`), so `Run.node_runtime(...)` can resolve a node function to its `FlowNode` without reaching into `Flow`'s private `_flow_nodes` list. This is the only new surface added to `Flow` itself; `Flow.__init__` gained no new attribute, and `Flow` still stores nothing about `NodeRuntime`s (verified structurally, same technique as Slice 2A's `vars(flow)` check). Module/class/`run()`-method docstrings updated to describe `NodeRuntime`'s existence and to remove now-stale claims that `NodeRuntime` "does not exist"/`Run` "owns no NodeRuntime".
4. `tests/test_slice_2b_node_runtime.py` (new) -- 9 focused tests: `run.node_runtime(node)` returns a `NodeRuntime`; the returned instance references the correct `FlowNode` and `Run`; repeated lookups on the same `Run` return the same instance; two `Run`s from the same `Flow` never share one; two distinct nodes in the same `Run` get distinct instances; an unregistered function raises `ValueError`; `FlowNode`'s own fields are unchanged (by value, via `dataclasses.fields`) after `NodeRuntime` lookups; `Flow`'s own instance state is unchanged (`vars(flow)` identity check, same technique as Slice 2A) and `Flow` has no `node_runtime`/`_node_runtimes` attribute; and `NodeRuntime` itself has no `.context`/`.memory`/`.last_output`/`.repository`/`.execute` yet.
5. `tests/test_slice_2a_flow_run.py` (modified) -- the Slice 2A negative test `test_run_has_no_execution_capability_yet` (which asserted `not hasattr(run, "node_runtime")`) was renamed to `test_run_has_no_publish_capability_yet` and narrowed to assert only `not hasattr(run, "publish")`, since `node_runtime` now legitimately exists as of this slice -- the same Test Integrity Rule precedent as Slice 1E's update to `tests/test_slice_1c_flow_node.py` and the Slice 2A follow-up's replacement of `test_run_has_no_repository_accessor_yet`: a stale negative assertion is corrected when the slice that makes it stale is the one doing the correcting, not silently left to fail or silently weakened.
6. No target architecture contract test moved -- confirmed in advance by reading all six remaining xfail test bodies (the one that reaches `NodeRuntime` at all, `test_run_instances_isolate_node_memory`, also requires `ctx.memory` and `.publish(...)`, both Milestone 2D/2E) and confirmed after implementation (`tests/test_target_architecture_contract.py` unchanged: 9 passed, 6 xfailed, zero XPASS). This matches `docs/refactor_priority_order.md`'s own Slice 2B row ("No target test moves alone").
7. `tests/test_current_regression_flow_runtime.py` (the old decorator `@flow` execution path) reconfirmed green and untouched: 3 passed.

Definition of done -- verified:

1. `run.node_runtime(node)` returns a `NodeRuntime`; the same node on the same `Run` returns the same instance; two `Run`s (even from one `Flow`) never share one; two distinct nodes in one `Run` get distinct instances (9/9 focused tests passed);
2. `FlowNode` acquired no Run-specific mutable execution state (verified structurally via `dataclasses.fields`); `Flow` acquired no `NodeRuntime` ownership (verified structurally via `vars(flow)` and explicit `hasattr` checks);
3. full suite: 97 passed (88 pre-existing + 9 new Slice 2B focused tests), 6 xfailed (unchanged) -- `uv run pytest -q -o addopts=''`;
4. target architecture contract: 9 passed, 6 xfailed, zero XPASS -- unchanged, a valid outcome explicitly anticipated by the task instructions and by `docs/refactor_priority_order.md`;
5. `tests/test_current_regression_flow_runtime.py` (the named regression guard for this slice): 3 passed, unchanged;
6. `uv run ruff check src tests` -- all checks passed;
7. blast radius: `git diff --stat` (against the committed `4fb0a76` baseline) shows `src/reed/composition/flow/flow_composition.py` grew from the post-2A-follow-up 65 inserted lines to 94 (the ~29-line delta being this slice's `flow_nodes` property and docstring updates); `src/reed/__init__.py` unchanged by this slice (`NodeRuntime` is not re-exported at the top level -- nothing requires it, since it is reached via `run.node_runtime(...)`, matching "prefer the smallest implementation"); `src/reed/execution/node_runtime.py` and `tests/test_slice_2b_node_runtime.py` are new, untracked files; `tests/test_slice_2a_flow_run.py` has exactly the one narrowing edit described above; nothing else changed;
8. architectural invariants re-confirmed: `FlowNode != NodeRuntime` (#2) and `NodeRuntime != NodeExecution` (#3, since `NodeExecution` does not exist) hold; `Flow != Run` (#4) and `Flow` owns no Run-specific execution state (#6) still hold with `NodeRuntime` ownership added to the picture; no Public Boundary invariant (#24-26) affected, since nothing new is exposed to node-function bodies;
9. no later Milestone 2 behavior was introduced: no argument construction from descriptors, no artifact-record unwrapping/wrapping, no `NodeContext` injection, no `NodeMemory`, no `ctx.memory`/`ctx.last_output`, no `NodeExecution`, no node-function execution, no `.publish(...)`, no transactional commit, no `on_output` dispatch (sync or async), no `callback_failures`, no stateful-firing serialization, no repository wiring into `NodeRuntime`, no `ArtifactRepository` rename, no new executors/schedulers/managers/factories/lifecycle frameworks.

### Slice 2C record (for reference)

Name:

```text
Domain Value <-> ArtifactRecord execution boundary -- ArtifactRecord[DomainType] plus NodeRuntime.unwrap(record)
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Milestone 2 Slice 2C row, Priorities 6/7, part of Priority 13; docs/parcel_boundary_decision.md; docs/architectural_invariants.md #7-11; this task's own instruction):

1. make `Domain Value != ArtifactRecord` concrete: `ArtifactRecord[DomainType]` with `value`/`version`/`provenance`;
2. node functions keep operating on domain values; Reed's execution/storage infrastructure operates on artifact records; the public node API stays domain-oriented and `ArtifactRecord` must not leak into node-function signatures;
3. reuse/migrate `Parcel`-era version/provenance mechanics only where this slice explicitly calls for it -- no broad Parcel -> Artifact rename;
4. integrate with `NodeRuntime` only to the extent this slice requires -- no full executor;
5. before implementing, derive the exact required fields/semantics of `ArtifactRecord`/`ArtifactVersion`/`ArtifactProvenance` from the accepted architecture and the existing `Parcel`-era implementation, not guesswork;
6. if `Depot`'s existing API cannot support the required boundary without an architectural choice or disproportionate migration, stop and report the mismatch rather than redesigning `Depot` or pulling Slice 3A forward.

Result (what was actually delivered):

1. `src/reed/execution/artifact_record.py` (new) -- `ArtifactVersion` (frozen, ordered dataclass; `.pending()` = 0, `.initial()` = 1, `.next()` returns a new instance), `ArtifactProvenance` (`producer: Optional[NodeRuntime] = None`, `version: ArtifactVersion` defaulting to `.pending()`, `dependencies: dict[type, ArtifactVersion]`, `.advance(*, producer=None, dependencies=None)` mutating in place, `.copy()`), and `ArtifactRecord[DomainType]` (`value: DomainType`, `provenance: ArtifactProvenance`, with delegating `.version`/`.dependencies` properties). All three mirror `reed.synchronization.parcel.provenance.ParcelVersion`/`ParcelProvenance`'s exact shape and behavior, adapted only where required: `ArtifactProvenance.producer` references a `NodeRuntime` (the new Run-scoped execution model) instead of the legacy `NodeId`, and `dependencies` is keyed by domain type rather than `Parcel` subclass type (Priority 7 item 4). `ArtifactRecord` wraps a domain value via composition (`.value` is a plain instance of the user's own type, zero Reed coupling) rather than the legacy `Parcel` inheritance model (`class RawImage(Parcel)`), matching `docs/parcel_boundary_decision.md`'s `unwrap: Parcel[T] -> T` / `wrap: U -> Parcel[U]` boundary diagram and `docs/implementation_refactor_assessment.md` #8's `ArtifactRecord[DomainType]` mapping.
2. `src/reed/execution/node_runtime.py` (modified) -- added `NodeRuntime.unwrap(record: ArtifactRecord) -> object`, a pure passthrough (`return record.value`). This is the entire `NodeRuntime` integration this slice performs: no repository read, no descriptor-based validation against the `FlowNode`'s consumed artifacts, and nothing calls it yet. `NodeRuntime` gained no execution responsibility; `Run`/`FlowNode`/`Flow` (`run.py`, `flow_composition.py`) were not modified at all in this slice (confirmed byte-identical to their post-2B state via sha256 and `git diff --stat`).
3. Deliberately did **not** rename `ParcelVersion`/`ParcelProvenance`/`Parcel` in place, despite `docs/refactor_priority_order.md` Priority 7 item 3's phrasing ("rename after `ArtifactRecord` exists"). This slice's own task instruction explicitly says not to perform the broad Parcel -> Artifact rename scheduled for later slices merely because `ArtifactRecord` now exists; `ArtifactVersion`/`ArtifactProvenance` are new, additive classes, following the same pattern already used for `TriggerPolicy` alongside untouched `PropagationPolicy` (Slice 1E) and `ArtifactDependencyGraph` alongside untouched `DependencyRegistry` (Slice 1D). Legacy `Parcel`/`ParcelVersion`/`ParcelProvenance`/`Depot`/`Outpost` (`src/reed/synchronization/`) are confirmed byte-for-byte untouched (`git diff --stat -- src/reed/synchronization/` is empty).
4. **Major finding, reported rather than silently resolved:** `Depot.set_parcel(...)` (`src/reed/synchronization/depot.py`) hard-checks `isinstance(parcel, Parcel)` and raises `TypeError` otherwise, so `run.repository` (`Depot`) structurally cannot hold an `ArtifactRecord` without either modifying `Depot`'s type contract (forbidden -- `Depot` is regression-protected legacy infrastructure, and that is exactly the kind of disproportionate migration this slice's instruction says to report rather than force) or making `ArtifactRecord` a `Parcel` subclass (architecturally backwards per `docs/non-goals.md`'s "ArtifactRecord Is Not A Blind Parcel Rename"). Resolved as non-blocking for this slice specifically: nothing commits an `ArtifactRecord` anywhere in Slice 2C (the task's own boundary diagram marks the wrap/repository direction "eventual", and `docs/refactor_priority_order.md` assigns "commit `ArtifactRecord`" to Slice 2E), so there is nothing that needs `Depot` to store one yet. Recorded as a new entry under "Open Architectural Questions" below for Slice 2E/3A to resolve. `run.repository` therefore does not participate in the `ArtifactRecord` boundary at all in this slice.
5. `tests/test_slice_2c_artifact_record.py` (new) -- 12 focused tests: `ArtifactRecord` wraps a domain value distinct from itself (composition, not inheritance); a fresh record defaults to a pending version, empty dependencies, and no producer; `ArtifactVersion` orders and advances exactly like `ParcelVersion` (pending < initial, `.next()`); `ArtifactProvenance.advance(...)` moves pending -> initial and only overwrites `producer`/`dependencies` when given (constructing a real `NodeRuntime` via `flow.run().node_runtime(...)` for the producer); `ArtifactProvenance.copy()` advances independently of its source; dependencies are keyed by domain type; `NodeRuntime.unwrap(record)` returns exactly the wrapped domain value by identity; `ArtifactRecord` has no `wrap`/`commit` capability yet and `NodeRuntime` has no `wrap` capability yet; and `Depot` (`run.repository`) still rejects a constructed `ArtifactRecord` with the same `TypeError` it raises for any non-`Parcel` value, directly guarding the finding in item 4 above.
6. No target architecture contract test moved -- confirmed in advance (none of the six remaining xfail tests construct or reference `ArtifactRecord`, and `run.repository.get(...)`, used by the 2F-tagged tests, still does not exist anywhere) and confirmed after implementation (`tests/test_target_architecture_contract.py` unchanged: 9 passed, 6 xfailed, zero XPASS). This matches `docs/refactor_priority_order.md`'s own Slice 2C row expectation.
7. `tests/test_current_regression_artifacts_repository.py` (the named regression guard for this slice, covering `Parcel.record_origin()`/`ParcelProvenance` version-advancing behavior) reconfirmed green and untouched: 6 passed.

Definition of done -- verified:

1. `ArtifactRecord[DomainType]` exists with `value`/`version`/`provenance`, `value` holding a plain domain instance (composition, `Domain Value != ArtifactRecord`, architectural_invariants.md #7); `ArtifactVersion`/`ArtifactProvenance` preserve `ParcelVersion`/`ParcelProvenance`'s exact mechanics, adapted only for `NodeRuntime` producers and domain-type-keyed dependencies (12/12 focused tests passed);
2. node-facing public API remains domain-oriented -- `ArtifactRecord` is not exposed through `NodeContext` and nothing in this slice changes any node-function signature;
3. `NodeRuntime` integration limited to a single pure `unwrap(record) -> record.value` passthrough; `NodeRuntime` acquired no execution responsibility; `Run`/`FlowNode`/`Flow` unchanged (byte-identical, verified via sha256 and `git diff --stat`);
4. `run.repository` (`Depot`) does not participate in the new boundary; the reason (Depot's `isinstance(parcel, Parcel)` type gate) is confirmed by a dedicated regression-style test and recorded under "Open Architectural Questions";
5. legacy `Parcel`/`ParcelVersion`/`ParcelProvenance`/`Depot`/`Outpost` confirmed unchanged: `tests/test_current_regression_artifacts_repository.py` -- 6 passed; `git diff --stat -- src/reed/synchronization/` -- empty;
6. full suite: 109 passed (97 pre-existing + 12 new Slice 2C focused tests), 6 xfailed (unchanged) -- `uv run pytest -q -o addopts=''`;
7. target architecture contract: 9 passed, 6 xfailed, zero XPASS -- unchanged, a valid outcome explicitly anticipated by this slice's own task instruction and by `docs/refactor_priority_order.md`;
8. `uv run ruff check src tests` -- all checks passed;
9. blast radius: new files `src/reed/execution/artifact_record.py` and `tests/test_slice_2c_artifact_record.py`; modified file `src/reed/execution/node_runtime.py` only (one method added, docstrings updated); `src/reed/execution/run.py` and `src/reed/composition/flow/flow_composition.py` untouched by this slice (confirmed via sha256 match against their post-2B content and via `git diff --stat` showing no further change since Slice 2B); nothing under `src/reed/synchronization/` touched;
10. architectural invariants re-confirmed: `Domain Value != ArtifactRecord` (#7) is now real via composition; `Artifact identity != artifact version` (#9) holds (`ArtifactRecord.version` is a distinct, delegated field, not identity); `ArtifactValue != ArtifactVersion`/`ArtifactValue != ArtifactProvenance` hold structurally (`value` and `provenance` are separate fields); `FlowNode != NodeRuntime` (#2) and `NodeRuntime != NodeExecution` (#3) still hold; Public Boundary invariants (#24-26) unaffected -- nothing new is exposed to node-function bodies;
11. no later Milestone 2 behavior was introduced: no `NodeContext` runtime state, no `ctx.memory`/`ctx.last_output`, no `NodeMemory`, no `NodeExecution`, no argument construction from descriptors, no node-function firing, no transactional commit, no `.publish(...)`, no `on_output` dispatch (sync or async), no `callback_failures`, no stateful-firing serialization, no `ArtifactRepository` rename, no new executors/schedulers/managers/factories/lifecycle frameworks.

### Slice 2D record (for reference)

Name:

```text
NodeContext runtime -- NodeRuntime-owned memory (lazily instantiated from MemoryType) plus a NodeContext(memory, last_output) snapshot
```

Status:

```text
COMPLETE (2026-09-12)
```

Goal (as planned, docs/refactor_priority_order.md Milestone 2 Slice 2D row, Priority 5, part of Priority 4, part of Priority 13; docs/node_context_decision.md; docs/architectural_invariants.md #12-17; this task's own instruction):

1. make `NodeContext`'s runtime semantics real: `ctx.memory` (private, node-local mutable state) and `ctx.last_output` (latest committed domain output for this NodeRuntime);
2. `NodeMemory` scope = `Run x NodeRuntime`: the same FlowNode materialized into different Runs must never share memory;
3. no runtime memory may live on `NodeDefinition`, `FlowNode`, `Flow`, the node function itself, or global/shared process state;
4. `ctx.last_output` must expose a domain value, not an `ArtifactRecord`, and must not be updated merely because a function returned a value absent a successful commit;
5. derive exact memory-initialization semantics from the accepted architecture rather than guessing, and stop and report if a genuine architectural choice is required and undetermined;
6. do not implement `NodeExecution`, node-function firing, argument construction, `ArtifactRecord` commit, repository commit semantics, transactional firing, `TriggerPolicy` execution eligibility, `on_output` dispatch, async callbacks, callback failure behavior, stateful firing serialization, or the `Depot` -> `ArtifactRepository` migration;
7. do not solve the Slice 2C repository-storage mismatch here -- carry it forward for Slice 2E.

Result (what was actually delivered):

1. `src/reed/composition/node/node_context.py` (modified) -- `NodeContext[MemoryType, OutputType]` (Slice 1A's empty `__slots__ = ()` shell) now has real state: `__init__(self, *, memory, last_output)` stores exactly the two values it is constructed with; `.memory` and `.last_output` are read-only properties returning them. `NodeContext` holds no reference back to `NodeRuntime`, `Run`, `Flow`, the repository, or the bus -- it is constructed fresh from plain values on each access (see item 2), so there is no path from `ctx` to any internal execution infrastructure at all, a stronger reading of docs/non-goals.md's "NodeContext Scope" ("must not become... a proxy to Run/Flow/Repository/Bus/Outpost or NodeRuntime") than merely omitting convenience properties.
2. `src/reed/execution/node_runtime.py` (modified) -- `NodeRuntime.__init__` gained `self._memory: object | None = None` and `self._last_output: object | None = None`. Three new properties: `.memory` (lazily instantiates `self._flow_node.context.memory_type()` -- a zero-argument construction, per `docs/refactor_priority_order.md` Priority 5's "instantiate memory from MemoryType" -- and memoizes it, so the same object, mutable in place, is returned on every subsequent access for this `NodeRuntime`'s lifetime); `.last_output` (returns `self._last_output`, always `None` in this slice); `.context` (returns `NodeContext(memory=self.memory, last_output=self.last_output)`, a fresh snapshot built from the two properties above). All three raise `AttributeError` -- not `ValueError` -- when `self._flow_node.context is None` (the node function declares no `NodeContext[...]` parameter at all, so there is no `MemoryType` to construct from); `AttributeError` is deliberate so `hasattr(node_runtime, "memory")` correctly reports `False` for such a node, since Python's `hasattr` only swallows `AttributeError`.
3. Memory isolation (`NodeMemory` scope = `Run x NodeRuntime`, architectural_invariants.md #14, #16) falls out structurally from Slice 2B's existing `NodeRuntime` ownership boundary (two `Run`s never share a `NodeRuntime`, Slice 2B) plus this slice's per-`NodeRuntime` memoization -- no additional isolation mechanism was needed or added. `FlowNode` and `Flow` remain unmodified by this slice and store no memory (verified structurally, same `dataclasses.fields`/`vars(flow)` technique as prior slices).
4. Memory-initialization semantics were derived, not guessed: `docs/node_context_decision.md` establishes the concept ("Memory = Memory(NodeRuntime, Run)") but does not itself state the exact construction mechanism; `docs/refactor_priority_order.md`'s Priority 5 "Recommended work" item 1 ("instantiate memory from `MemoryType`") does, and nothing at a higher authority rank (ADRs, architectural_invariants.md, non-goals.md) contradicts a zero-argument `MemoryType()` construction -- consistent with every `TrackerMemory`-shaped example in `docs/node_context_decision.md` and `tests/test_target_architecture_contract.py`, all of which have every field defaulted. This did not require stopping and reporting a materially undetermined choice; it is documented here as the derivation rather than an invented convenience.
5. `ctx.last_output`'s initial semantics: always `None`, matching `docs/node_context_decision.md`'s "Strong Typing Rule" (`ctx.last_output` is statically `OutputType | None`) and `tests/test_target_architecture_contract.py::test_last_output_exposes_latest_committed_domain_value`'s own `seen_previous[0] is None` assertion for a first firing. Nothing in this slice sets it to anything else -- there is no commit mechanism yet (Slice 2E) -- satisfying "must not be updated merely because a function returned a value if no successful commit has occurred" by construction (nothing calls the node function at all in this slice).
6. `tests/test_slice_2d_node_context.py` (new) -- 13 focused tests: memory is instantiated from the declared `MemoryType` via zero-argument construction; memory is memoized (same object, mutable in place) across repeated `NodeRuntime.memory`/`.context` accesses; two `Run`s from the same `Flow` have independent memory (mutating one does not affect the other); repeated `run.node_runtime(...)` lookups on one `Run` share memory (via Slice 2B memoization); `FlowNode` and `Flow` store no memory; `ctx.last_output` is `None` before any commit; `NodeContext` exposes no `run`/`flow`/`flow_node`/`node_runtime`/`repository`/`bus`/`outpost` attribute, public or private; `NodeRuntime.memory`/`.context`/`.last_output` raise `AttributeError` (and correctly report `False` to `hasattr`) for a node declaring no `NodeContext` parameter; `NodeRuntime.context` returns a `NodeContext` instance; `NodeContext()` cannot be constructed without its required `memory`/`last_output` keyword arguments; and no execution, commit, or repository capability was introduced (`run.publish`, `node_runtime.execute`/`.commit`/`.fire`, `ctx.commit`/`.wrap`/`.unwrap` all absent).
7. Two prior slices' negative tests were corrected in place (Test Integrity Rule -- this slice is exactly the one making them stale, per the same precedent as Slices 1E, 2A follow-up, and 2B): `tests/test_slice_2b_node_runtime.py::test_node_runtime_has_no_execution_capability_yet` (renamed to `test_node_runtime_has_no_repository_or_execution_capability_yet`, narrowed to keep only its still-true `repository`/`execute` assertions -- its `context`/`memory`/`last_output` assertions happened to still literally pass for that test's context-less node, via the `AttributeError` design in item 2, but leaving its docstring/name claiming categorical absence of those capabilities would have been misleading now that they are real properties elsewhere); `tests/test_slice_1a_domain_signature_parsing.py::test_node_context_shell_has_no_runtime_behavior` (renamed to `test_node_context_shell_is_generic_and_detectable`, its `NodeContext.__slots__ == ()` assertion removed since `NodeContext` now genuinely has slots/runtime behavior -- this was Slice 1A's own explicit prediction of what would eventually make it stale, now realized). Both files' full suites re-confirmed passing after the edits (9/9 and 10/10 respectively).
8. No target architecture contract test moved -- confirmed in advance (both `test_run_instances_isolate_node_memory` and `test_last_output_exposes_latest_committed_domain_value` call `run.publish(...)`, which does not exist until Slice 2E's firing pipeline) and confirmed after implementation (`tests/test_target_architecture_contract.py` unchanged: 9 passed, 6 xfailed, zero XPASS). This matches `docs/refactor_priority_order.md`'s own Slice 2D row ("No target test moves alone... `ctx.last_output` needs a commit to report").
9. `tests/test_current_regression_flow_runtime.py` (the old decorator `@flow` execution path, the relevant regression guard here since no dedicated NodeContext regression file exists) reconfirmed green and untouched: 3 passed.
10. The Slice 2C repository-storage mismatch (Open Architectural Questions) was deliberately left untouched: `run.repository`/`Depot` were not read from, written to, or modified by anything in this slice.

Definition of done -- verified:

1. `ctx.memory` and `ctx.last_output` are real (13/13 focused tests passed); `ctx.memory` is private, node-local, mutable state persisting across firings within one Run (memoization); `ctx.last_output` is the latest committed domain output for this NodeRuntime, always `None` in this slice;
2. `NodeMemory` scope = `Run x NodeRuntime` verified directly: two `Run`s from the same `Flow`, same node, have independent, non-identical memory instances; repeated lookups on one `Run` share memory;
3. no runtime memory lives on `NodeDefinition`, `FlowNode`, `Flow`, the node function, or global/shared process state (verified structurally for `FlowNode`/`Flow`, and by construction for `NodeDefinition`/the function itself -- neither was modified);
4. `ctx.last_output` exposes only a domain value type (`OutputType | None`), never an `ArtifactRecord`; nothing updates it in this slice, satisfying "must not be updated merely because a function returned a value if no successful commit has occurred" by there being no execution at all yet;
5. memory-initialization semantics were derived from `docs/refactor_priority_order.md`'s Priority 5 ("instantiate memory from MemoryType") rather than invented, with no contradiction found at any higher-authority document -- no stop-and-report was required;
6. no `NodeExecution`, node-function firing, argument construction, `ArtifactRecord` commit, repository commit semantics, transactional firing, `TriggerPolicy` execution eligibility, `on_output` dispatch, async callbacks, callback failure behavior, stateful firing serialization, or `Depot` -> `ArtifactRepository` migration was introduced;
7. the Slice 2C repository-storage mismatch (Open Architectural Questions) remains exactly as recorded, untouched by this slice;
8. full suite: 122 passed (109 pre-existing + 13 new Slice 2D focused tests), 6 xfailed (unchanged) -- `uv run pytest -q -o addopts=''`;
9. target architecture contract: 9 passed, 6 xfailed, zero XPASS -- unchanged, a valid outcome explicitly anticipated by this slice's own task instruction and by `docs/refactor_priority_order.md`;
10. `uv run ruff check src tests` -- all checks passed;
11. blast radius: modified `src/reed/composition/node/node_context.py` (real `__init__`/properties added) and `src/reed/execution/node_runtime.py` (three new properties); modified (corrected) `tests/test_slice_2b_node_runtime.py` and `tests/test_slice_1a_domain_signature_parsing.py` (one stale negative test each); new `tests/test_slice_2d_node_context.py`; `src/reed/execution/run.py`, `src/reed/execution/artifact_record.py`, `src/reed/composition/flow/flow_composition.py`, and everything under `src/reed/synchronization/` untouched (confirmed via `git diff --stat` and unchanged file modification times on-device);
12. architectural invariants re-confirmed: `NodeContext != InputPort` (#12, unchanged from Slice 1A) still holds; `NodeContext` exposes only `memory`/`last_output` (#13) is now concretely true (verified by the no-internal-infrastructure test); `NodeMemory` belongs to `Run x NodeRuntime` (#14) and different Runs do not share it (#16) are both now real and directly tested; `NodeMemory != last_output` (#15) holds structurally (two separate properties/slots, never conflated); stateful-firing serialization (#17) is not yet applicable (nothing executes concurrently, or at all, in this slice); Public Boundary invariants (#24-26) hold -- `NodeContext` exposes nothing beyond `memory`/`last_output`, confirmed by an explicit test asserting the absence of every internal-infrastructure attribute considered.

## Completed Slices

| Slice | Commit | Tests changed | Result |
|---|---|---|---|
| 1A | (uncommitted; working tree dirty) | `tests/test_slice_1a_domain_signature_parsing.py` added (10 passing tests); all pre-existing regression and target-contract tests unchanged | Typed domain signature parsing implemented (`domain_signature.py`); minimal structural `NodeContext` shell implemented (`node_context.py`); `NodeContext` excluded from dataflow inputs; `NodeContext` output type validated against return type; self-flow rejected at signature level. No target architecture test moved (none could -- all gate on Slice 1F). See "Slice 1A record" above for full detail. |
| 1B | (uncommitted; working tree dirty) | `tests/test_slice_1b_domain_node_description.py` added (7 passing tests); all pre-existing regression, target-contract, and Slice 1A tests unchanged | `ArtifactDescriptor`/`ArtifactRole` implemented (`artifact_descriptor.py`); domain-typed `DomainNodeDescription`/`DomainNodeDefinition`/`NodeContextDescriptor`/`DomainNodeDescriptionBuilder` implemented (`domain_node_description.py`), reusing Slice 1A's signature parser for validation. No target architecture test moved (1B is a prerequisite for 1C-1F). See "Slice 1B record" above for full detail. |
| 1C | (uncommitted; working tree dirty) | `tests/test_slice_1c_flow_node.py` added (7 passing tests); all pre-existing regression, target-contract, and Slice 1A/1B tests unchanged | `FlowNode` implemented (`flow_node.py`): flow-local node participation holding a `DomainNodeDefinition`, exposing consumed/produced artifact descriptors and an optional `NodeContext` descriptor, and storing `trigger_policy` (typed against the existing `PropagationPolicy` enum) and `on_output`. No target architecture test moved (nothing reaches `FlowNode` publicly until Slice 1F). `TriggerPolicy` rename (1E) and `DependencyRegistry` migration (1D) were explicitly not absorbed. See "Slice 1C record" above for full detail. |
| 1D | (uncommitted; working tree dirty) | `tests/test_slice_1d_artifact_dependency_graph.py` added (8 passing tests); all pre-existing regression, target-contract, and Slice 1A/1B/1C tests unchanged; old `DependencyRegistry`'s 2 regression tests unaffected | `ArtifactDependencyGraph` implemented (`artifact_dependency_graph.py`): `DependencyRegistry` migrated to `FlowNode`/domain-artifact-type vocabulary, preserving unique-producer validation and adding self-flow validation at registration time. Old `DependencyRegistry` untouched (confirmed byte-identical). No target architecture test moved (not wired into any Flow-composition entry point until Slice 1F). `TriggerPolicy` migration (1E) and `Flow.add(...)` (1F) were explicitly not absorbed. See "Slice 1D record" above for full detail. |
| 1E | (uncommitted; working tree dirty) | `tests/test_slice_1e_trigger_policy.py` added (9 passing tests); `tests/test_slice_1c_flow_node.py` updated in place (7 tests, still passing, now asserting against `TriggerPolicy`); all pre-existing regression, target-contract, and Slice 1A/1B/1D tests unchanged | `TriggerPolicy` introduced (`trigger_policy.py`): target enum (`ANY_INPUT_CHANGED`/`ALL_INPUTS_CHANGED`/`MANUAL`) plus an unused-by-execution `from_propagation_policy(...)` mapping. `FlowNode.trigger_policy` (Slice 1C) retyped from `PropagationPolicy` to `TriggerPolicy`, completing the ownership relocation `refactor_priority_order.md` assigned to this slice. Old `PropagationPolicy`/`NodeDefinition`/`Node` untouched (confirmed byte-identical); their execution-eligibility logic is unmodified. No target architecture test moved (still gated on Slice 1F). Execution-logic wiring, `Flow.add(...)`, and callback dispatch were explicitly not absorbed. See "Slice 1E record" above for full detail. |
| 1F | (uncommitted; working tree dirty) | `tests/test_target_architecture_contract.py` modified in place (xfail-scope only: the module-level blanket marker removed, 9 tests now unmarked/passing, 6 re-marked `xfail` with per-test Milestone-2 reasons); no new dedicated Slice 1F test file -- the target contract file itself is the focused verification; all pre-existing regression and Slice 1A-1E tests unchanged | `Flow.add(...)` implemented (`flow_composition.py`, new `reed.Flow`), wiring `NodeDefinition -> Flow.add(...) -> FlowNode -> ArtifactDependencyGraph`; top-level `reed.flow` re-export added; `reed/__init__.py` exports `Flow`/`TriggerPolicy`/`NodeContext`. All nine Milestone-1 target architecture contract tests now pass; the six Milestone-2 tests remain `xfail` (they call `flow.run()`, which does not exist -- no special-casing needed). A real annotation-resolution gap in Slice 1A's `domain_signature.py` (local-scope `NodeContext` imports not visible to `get_type_hints`) was discovered and fixed via an additive, default-`None` `extra_globalns` parameter threaded from `Flow.add(...)`'s caller frame -- not Milestone-2 scope. See "Slice 1F record" above for full detail. |
| 2A | (uncommitted; working tree dirty; Milestone 1 through 1F is committed at `4fb0a76`) | `tests/test_slice_2a_flow_run.py` added (9 passing tests); `tests/test_target_architecture_contract.py` unchanged (9 passed, 6 xfailed, zero XPASS -- no target test assigned to this slice); `tests/test_current_regression_flow_runtime.py` unchanged (3 passed) | `Run` implemented (`src/reed/execution/run.py`, new `reed.Run`): a minimal identity/ownership boundary holding only a back-reference to its originating `Flow`. `Flow.run()` added (`flow_composition.py`): returns a new `Run` per call; `Flow` stores no Run-specific state (verified structurally). `Flow != Run` (architectural_invariants.md #4, #6) is now real. No target architecture test moved (valid, predicted outcome). A documented scope conflict was initially resolved by deferring `.repository`; a Pre-2B Review found that deferral overly conservative, and a same-day Slice 2A follow-up corrected it: each `Run` now constructs and owns its own `Depot`-backed repository instance, exposed as `run.repository` (see "Slice 2A record" above for full detail). `NodeRuntime`, `ArtifactRecord` wrap/unwrap, `NodeContext` runtime behavior, `ctx.memory`/`ctx.last_output`, `NodeExecution`, commit semantics, `on_output` dispatch, callback failure handling, stateful firing serialization, and `ArtifactRepository` migration were explicitly not absorbed. See "Slice 2A record" above for full detail. |
| 2B | (uncommitted; working tree dirty; Milestone 1 through 1F is committed at `4fb0a76`) | `tests/test_slice_2b_node_runtime.py` added (9 passing tests); `tests/test_slice_2a_flow_run.py` updated in place (one stale negative assertion narrowed, all 14 tests still passing); `tests/test_target_architecture_contract.py` unchanged (9 passed, 6 xfailed, zero XPASS -- no target test assigned to this slice); `tests/test_current_regression_flow_runtime.py` unchanged (3 passed) | `NodeRuntime` implemented (`src/reed/execution/node_runtime.py`, new): a minimal identity/ownership boundary holding a back-reference to its owning `Run` and to the `FlowNode` it materializes. `Run.node_runtime(node)` added (`run.py`): get-or-create, memoized per `Run`, resolving `node` (the original callable) to its `FlowNode` via a new read-only `Flow.flow_nodes` property (`flow_composition.py`). Two `Run`s never share a `NodeRuntime`; repeated lookups on one `Run` return the same instance; `FlowNode` and `Flow` acquire no Run-specific state (both verified structurally). `FlowNode != NodeRuntime` (architectural_invariants.md #2) is now real. No target architecture test moved (valid, predicted outcome, matching `docs/refactor_priority_order.md`'s Slice 2B row). No argument construction, unwrapping, `NodeContext` injection, `NodeMemory`, execution, commit, or callback dispatch were absorbed. See "Slice 2B record" above for full detail. |

| 2C | (uncommitted; working tree dirty; Milestone 1 through 1F is committed at `4fb0a76`) | `tests/test_slice_2c_artifact_record.py` added (12 passing tests); `tests/test_current_regression_artifacts_repository.py` unchanged (6 passed); `tests/test_target_architecture_contract.py` unchanged (9 passed, 6 xfailed, zero XPASS -- no target test assigned to this slice); `tests/test_current_regression_flow_runtime.py` unchanged (3 passed) | `ArtifactRecord[DomainType]` implemented (`src/reed/execution/artifact_record.py`, new): a composition-based wrapper (`value`/`provenance`, delegating `.version`/`.dependencies`) distinct from the legacy inheritance-based `Parcel`. `ArtifactVersion`/`ArtifactProvenance` preserve `ParcelVersion`/`ParcelProvenance`'s exact versioning/provenance mechanics, adapted for `NodeRuntime` producers and domain-type-keyed dependencies; legacy `Parcel`/`Depot`/`Outpost` confirmed byte-for-byte untouched. `NodeRuntime.unwrap(record)` added (`node_runtime.py`): a pure `record.value` passthrough, the only `NodeRuntime` integration this slice performs. `Domain Value != ArtifactRecord` (architectural_invariants.md #7) is now real. No target architecture test moved (valid, predicted outcome). Major reported finding: `Depot.set_parcel(...)`'s hard `Parcel`-type check means `run.repository` structurally cannot hold an `ArtifactRecord` yet -- recorded as a new Open Architectural Question for Slice 2E/3A, since nothing commits an `ArtifactRecord` in this slice. `NodeContext` runtime behavior, `ctx.memory`/`ctx.last_output`, `NodeMemory`, `NodeExecution`, node-function firing, transactional commit, `on_output` dispatch, callback handling, stateful-firing serialization, and `ArtifactRepository` migration were explicitly not absorbed. See "Slice 2C record" above for full detail. |
| 2D | (uncommitted; working tree dirty; Milestone 1 through 1F is committed at `4fb0a76`) | `tests/test_slice_2d_node_context.py` added (13 passing tests); `tests/test_slice_2b_node_runtime.py` and `tests/test_slice_1a_domain_signature_parsing.py` each updated in place (one stale negative assertion corrected each, all tests still passing: 9/9 and 10/10); `tests/test_target_architecture_contract.py` unchanged (9 passed, 6 xfailed, zero XPASS -- no target test assigned to this slice); `tests/test_current_regression_flow_runtime.py` unchanged (3 passed) | `NodeContext[MemoryType, OutputType]` (Slice 1A's `__slots__ = ()` shell) gained real `ctx.memory`/`ctx.last_output` values (`node_context.py`): both are plain, read-only properties over values the instance is constructed with, with no back-reference to `NodeRuntime`/`Run`/`Flow`/repository/bus at all. `NodeRuntime` (`node_runtime.py`) gained `.memory` (lazily instantiated from the FlowNode's declared `MemoryType` via zero-argument construction, memoized per `NodeRuntime`), `.last_output` (always `None` -- no commit exists yet), and `.context` (a fresh `NodeContext` snapshot built from both). `NodeMemory` scope = `Run x NodeRuntime` (architectural_invariants.md #14, #16) falls out of Slice 2B's existing `NodeRuntime` isolation plus this slice's per-instance memoization; `FlowNode`/`Flow` store no memory (verified structurally). No target architecture test moved (both remaining relevant xfail tests require `run.publish(...)`, Slice 2E). The Slice 2C repository-storage mismatch was left untouched, as instructed. See "Slice 2D record" above for full detail. |

## Target Contract Status

(Renamed from "Remaining Target Contracts" -- as of Slice 1F, nine of
the fifteen target contracts are delivered, not remaining. Slice 2A
did not move any of the remaining six -- this table is unchanged from
Slice 1F and matches `docs/refactor_priority_order.md`'s own
prediction for 2A.)

| Contract | Test | Status |
|---|---|---|
| `Flow.add(...)` returns a `FlowNode` | `test_flow_add_registers_callable_and_returns_flownode` | passing (Slice 1F) |
| `TriggerPolicy` is stored on `FlowNode` | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` | passing (Slice 1F) |
| `on_output` is stored on `FlowNode` | `test_flow_add_uses_keyword_only_trigger_policy_and_on_output` | passing (Slice 1F) |
| `Flow.add(...)` rejects positional configuration ambiguity | `test_flow_add_rejects_positional_configuration_ambiguity` | passing (Slice 1F) |
| Node signatures use domain types rather than artifact records | `test_node_signature_uses_domain_types_not_artifact_records` | passing (Slice 1F) |
| `NodeContext` is injected and excluded from input ports | `test_node_context_is_injected_and_not_registered_as_input_port` | passing (Slice 1F) |
| `NodeContext[MemoryType, OutputType]` must match the return type | `test_node_context_output_type_must_match_return_type` | passing (Slice 1F) |
| Duplicate output domain type is rejected in one Flow | `test_duplicate_output_domain_type_is_rejected_in_one_flow` | passing (Slice 1F) |
| Self-flow signatures are rejected | `test_self_flow_signature_is_rejected` | passing (Slice 1F) |
| Distinct output artifact types allow safe branching | `test_parallel_safe_branching_uses_distinct_output_artifact_types` | passing (Slice 1F) |
| Run instances isolate node memory | `test_run_instances_isolate_node_memory` | xfail (Milestone 2, Slice 2E) |
| `ctx.last_output` exposes the latest committed domain value | `test_last_output_exposes_latest_committed_domain_value` | xfail (Milestone 2, Slice 2E) |
| `on_output` runs after commit and receives the domain value | `test_on_output_runs_after_commit_and_receives_domain_value` | xfail (Milestone 2, Slice 2F) |
| async `on_output` is supported after commit | `test_async_on_output_is_supported_after_commit` | xfail (Milestone 2, Slice 2F) |
| callback failure does not undo committed output | `test_callback_failure_does_not_undo_committed_output` | xfail (Milestone 2, Slice 2F) |
| stateful `NodeRuntime` firings are serialized | `test_stateful_node_runtime_firings_are_serialized` | xfail (Milestone 2, Slice 2G) |

## Known Compatibility Layer

The following existing APIs and behaviors remain supported during the early refactor:

1. `@flow`;
2. `@input`;
3. `@node`;
4. `@output`;
5. Parcel-based node signatures;
6. current `FlowFactory` creation behavior;
7. current synchronous decorator-based flow execution.

Rules:

1. existing Parcel-based regression tests must remain green until an explicit architectural migration supersedes them;
2. compatibility aliases may be introduced when useful;
3. compatibility aliases must not hide the new architectural boundaries;
4. old decorators must not be removed in the first implementation pass.

## Known Conflicts Between Current Implementation And Target Architecture

| Area | Current implementation | Target architecture | Handling |
|---|---|---|---|
| Node boundary | User functions consume and produce `Parcel` subclasses at runtime; `ArtifactRecord[DomainType]` (Slice 2C) now exists as the target-side record representation but is not yet wired into any node-function call. | User functions consume and produce domain values. | Preserve regression tests; target tests remain xfail until wrap/commit and argument construction exist (2E). |
| Artifact identity | Parcel subclass currently acts as dependency identity at runtime; `ArtifactRecord.dependencies` (Slice 2C) is already keyed by domain type, not by Parcel subclass. | Domain type is the semantic artifact identity. | Artifact descriptors (1B) and `ArtifactRecord` (2C) both already use domain-type keys; broad renaming of the runtime dependency path remains for later slices. |
| Flow API | Flow is created through `@flow` and `FlowFactory`. | `Flow` is an explicit composition object with `Flow.add(...)`. | Introduce new API alongside compatibility path. |
| Flow-local participation | No explicit `FlowNode`. | `Flow.add(...)` returns `FlowNode`. | Add `FlowNode` before moving policy and callbacks. |
| Trigger policy ownership | `PropagationPolicy` lives on `NodeDefinition`. | `TriggerPolicy` belongs to `FlowNode`. | Move ownership after `FlowNode` exists. |
| Context injection | `NodeContext[MemoryType, OutputType]` exists, is excluded from input ports (Slice 1A), and now has real `ctx.memory`/`ctx.last_output` values (Slice 2D); nothing constructs/injects one into an actual node-function call yet. | `NodeContext[MemoryType, OutputType]` is injected and excluded from input ports. | Detection/exclusion done (1A); runtime values done (2D); injection into a real node call remains 2E. |
| Local memory | `NodeRuntime.memory` (Slice 2D) is a real, scoped-to-`Run x NodeRuntime` memory boundary, exposed read-only through `ctx.memory`; nothing writes to it except the user's own node-function body once execution exists (2E). | `NodeMemory` belongs to `Run x NodeRuntime`. | Introduced (2D); wiring memory access into a real node-function call remains 2E. |
| Runtime ownership | Current `Node` owns execution and `Outpost`; `NodeRuntime` (Slice 2B) is an ownership boundary created and held by `Run`, with one pure `unwrap(record) -> record.value` step (Slice 2C) and now its own memory/last_output/context (Slice 2D); still no execution capability. | `NodeRuntime` owns run-local execution for a `FlowNode`. | Ownership boundary established (2B); unwrap boundary established (2C); memory/context established (2D); argument construction, execution, and commit remain 2E; old `Node`/`Outpost` still do the real work today. |
| Repository name | `Depot` stores current Parcels; `ArtifactRecord` (Slice 2C) is real but `Depot.set_parcel(...)` hard-rejects any non-`Parcel` value, so `Depot` structurally cannot yet hold one (see Open Architectural Questions). | `ArtifactRepository` stores artifact records. | `ArtifactRecord` is real (2C); rename/storage-capability decision deferred to Slice 2E (commit) or 3A (`Depot` -> `ArtifactRepository`). |
| Outpost role | `Outpost` is a broad synchronization component. | It should become internal to `NodeRuntime` or an adapter. | Do not rename to `NodeMemory`; postpone until ownership is clear. |

## Open Architectural Questions

**RESOLVED 2026-09-12 (human decision, not agent-derived).** The question below -- "How will `run.repository` come to hold an `ArtifactRecord`?" -- was escalated by a `reed-architect` invocation attempting Slice 2E under the Reed Agentic Refactor Workflow, which correctly wrote `HUMAN_DECISION_REQUIRED` rather than guessing among the alternatives recorded below. A human then accepted alternative (b): `Depot` gains a separate, additive `ArtifactRecord` storage path keyed by `type(record.value)`, alongside its existing, untouched `Parcel` storage; the committed `ArtifactRecord` is the authoritative shared state, `NodeRuntime.last_output` is a synchronized local view of it, and the `Depot -> ArtifactRepository` rename remains Slice 3A's alone. See `docs/parcel_boundary_decision.md`'s "Addendum: Slice 2E ArtifactRecord Commit Storage" for the full accepted decision. The record below is kept for history -- it is what made the decision necessary, not what determines it going forward.

**How will `run.repository` come to hold an `ArtifactRecord`?**
(Recorded during Slice 2C; a prior `Run.repository` question raised
during Slice 2A was resolved the same day by a Pre-2B Review and a
Slice 2A follow-up -- see the Slice 2A record above and the Refactor
State Log for that history. This is a new, separate question.
Confirmed still unresolved and untouched by Slice 2D: `NodeContext`'s
new `ctx.memory`/`ctx.last_output` values are constructed entirely
from `NodeRuntime` state -- nothing in Slice 2D reads from or writes
to `run.repository`/`Depot`, as instructed.)

1. Blocking slice: Slice 2E ("commit `ArtifactRecord`", per
   `docs/refactor_priority_order.md`'s Milestone 2 table) at the
   earliest, or Slice 3A (the `Depot` -> `ArtifactRepository`
   migration) if the decision is deferred that far.
2. Missing decision: `Depot.set_parcel(self, parcel)` hard-checks
   `isinstance(parcel, Parcel)` and raises `TypeError` for anything
   else, so `run.repository` (still `Depot`-backed as of Slice 2A's
   follow-up) cannot store an `ArtifactRecord` today. No accepted
   document says whether Slice 2E should (a) widen `Depot`'s type
   contract in place, (b) introduce a new Run-scoped storage type
   that Slice 3A later folds into `ArtifactRepository`, or (c) pull
   part of the `Depot` -> `ArtifactRepository` rename (Slice 3A)
   earlier than planned so the new repository type can hold
   `ArtifactRecord`s from the start.
3. Why it matters: Slice 2E's own scope ("commit `ArtifactRecord`")
   cannot be implemented without deciding how/where a committed
   `ArtifactRecord` is actually stored -- this is exactly the kind of
   materially-different-semantics choice `docs/refactor_agent_
   protocol.md` requires stopping and reporting on rather than
   guessing.
4. Alternatives discovered: widening `Depot`'s type check was
   rejected for Slice 2C itself as a disproportionate migration of
   regression-protected legacy infrastructure; making `ArtifactRecord`
   a `Parcel` subclass was rejected as architecturally backwards
   (`docs/non-goals.md`, "ArtifactRecord Is Not A Blind Parcel
   Rename"). Neither alternative was adopted; both are recorded here
   for whoever plans Slice 2E/3A.
5. Affected tests: `tests/test_slice_2c_artifact_record.py::
   test_depot_still_rejects_non_parcel_values_including_artifact_record`
   pins today's rejecting behavior; the 2F-tagged target contract
   tests (`test_on_output_runs_after_commit_and_receives_domain_value`,
   `test_callback_failure_does_not_undo_committed_output`) already
   assume a working `run.repository.get(domain_type) -> ArtifactRecord`
   accessor that does not exist yet and will need this question
   resolved first.
6. Affected classes: `Depot` (`src/reed/synchronization/depot.py`),
   `ArtifactRecord`/`ArtifactProvenance`/`ArtifactVersion`
   (`src/reed/execution/artifact_record.py`), `Run.repository`
   (`src/reed/execution/run.py`), and eventually
   `ArtifactRepository` (not yet created).

When another open question is added, it must include the same six
fields:

1. the blocking slice;
2. the missing decision;
3. why implementation depends on it;
4. alternatives discovered;
5. affected tests;
6. affected classes.

## Next Recommended Slice

Now that Slice 2D has completed, `ctx.memory` and `ctx.last_output`
are real (`NodeRuntime`-owned, `Run x NodeRuntime`-scoped memory;
`NodeContext` a plain read-only snapshot over it):

```text
Slice 2E -- NodeExecution firing pipeline: argument construction, node-function execution, ArtifactRecord wrap/commit, ctx.last_output wired to a real committed value
(docs/refactor_priority_order.md, Milestone 2, Slice 2E row)
```

Per `docs/refactor_priority_order.md`'s Milestone 2 table, Slice 2E is
the first slice that can move a target architecture contract test:
`test_run_instances_isolate_node_memory` and
`test_last_output_exposes_latest_committed_domain_value` both call
`run.publish(...)`, which does not exist until 2E builds the real
firing pipeline (unwrap `ArtifactRecord`s into domain values via
`NodeRuntime.unwrap` (2C), build a node function's call arguments
including its `NodeContext` (2D) if declared, execute the function,
wrap its returned domain value into a committed `ArtifactRecord`, and
update `ctx.last_output`/`ctx.memory` together with that commit per
docs/node_context_decision.md's "Transaction Semantics").

The Open Architectural Question recorded during Slice 2C, which
became blocking exactly at this point, is now **resolved** (see "Open
Architectural Questions" above and `docs/parcel_boundary_decision.md`'s
Slice 2E addendum): a `reed-architect` invocation correctly escalated
rather than guessing, and a human accepted alternative (b) -- `Depot`
gains a separate, additive `ArtifactRecord` storage path keyed by
`type(record.value)`, alongside its existing untouched `Parcel` storage;
the committed `ArtifactRecord` is authoritative shared state,
`NodeRuntime.last_output` is a synchronized local view of it, and the
`Depot -> ArtifactRepository` rename remains Slice 3A's alone. Slice 2E
may now proceed to implement "commit `ArtifactRecord`" against that
accepted storage decision.

This is a recommendation, not an authorization. Starting Slice 2E still
requires a new explicit task (see the One-Slice Termination Rule in
`refactor_agent_protocol.md`).

## Refactor State Log

| Date | Change |
|---|---|
| 2026-09-12 | Baseline test safety net created: 24 passing regression tests and 15 expected target-architecture failures. |
| 2026-09-12 | `refactor_state.md` expanded into the live operational checkpoint for the refactor. |
| 2026-09-12 | Development environment verified with `uv`: `uv run pytest -q` reports 24 passed, 15 xfailed, 86% coverage; `uv run ruff check src tests` passes. |
| 2026-09-12 | `refactor_agent_protocol.md` added as the operational protocol for AI agents executing the refactor. |
| 2026-09-12 | Refactor documentation harness audited and restructured: `architectural_invariants.md` added to required reading; `refactor_priority_order.md`'s single "first implementation slice" split into Milestone 1 / Milestone 2 with lettered slices; authority order made explicit in `refactor_guide.md`. Baseline re-verified in this session: `uv run pytest -q -o addopts=''` reports 24 passed, 15 xfailed; `uv run ruff check src tests` passes. Coverage percentage not re-measured this session (sandbox could not write `.coverage` in the mounted working tree); this does not affect pass/fail counts. |
| 2026-09-12 | Slice decomposition refined (no architecture changed): fixed a real dependency bug (`NodeContext` shell must exist before signature parsing can detect it -- moved into 1A; `FlowNode` must exist before `DependencyRegistry` migrates to its vocabulary -- reordered before it); moved `NodeMemory` (needs `Run x NodeRuntime`) and `ArtifactRecord` (needs the execution boundary) out of Milestone 1 into Milestone 2, where they are actually consumed; split Milestone 2 into seven smaller slices (2A-2G) along its "and"-clause seams; added a new Milestone 3 ("Infrastructure Alignment") for `ArtifactRepository` and the remaining cross-cutting vocabulary work, previously misplaced inside Milestone 2. Milestone 1 is now 1A-1F (was 1A-1H). Confirmed every Milestone-1 target test gates on Slice 1F (`Flow.add(...)`) and corrected "Target tests expected to move" for the current slice (1A) from four tests to none. Baseline re-verified again: 24 passed, 15 xfailed, ruff clean; `src/` untouched. |
| 2026-09-12 | Slice 1A implemented: added `src/reed/composition/node/domain_signature.py` (`DomainNodeSignatureParser`/`DomainNodeSignature` -- typed domain signature parsing, `NodeContext` detection/exclusion, `NodeContext` output-type validation, self-flow rejection) and `src/reed/composition/node/node_context.py` (minimal structural `NodeContext[MemoryType, OutputType]` shell, no runtime behavior, not yet exposed at the `reed` package top level). Both are additive: no existing production file was modified, so the old Parcel-centric `NodeDescriptionBuilder` path is untouched and its regression tests remain green. Added `tests/test_slice_1a_domain_signature_parsing.py` (10 new passing tests) since no target-architecture test can move before Slice 1F. Full suite: 34 passed (24 pre-existing + 10 new), 15 xfailed (unchanged); `ruff check src tests` clean. Slice 1A marked COMPLETE; no further slice authorized. |
| 2026-09-12 | Slice 1B implemented: added `src/reed/composition/node/artifact_descriptor.py` (`ArtifactRole`/`ArtifactDescriptor` -- identity-only domain artifact descriptor, distinct from `ArtifactRecord`) and `src/reed/composition/node/domain_node_description.py` (`NodeContextDescriptor`/`DomainNodeDescription`/`DomainNodeDefinition`/`DomainNodeDescriptionBuilder` -- domain-typed node description/definition storing artifact descriptors instead of Parcel-centered metadata, with no flow-local policy/callback/execution state on the definition). Builder reuses Slice 1A's `DomainNodeSignatureParser` for all validation rather than duplicating it. Both files are additive: no existing production file was modified. Added `tests/test_slice_1b_domain_node_description.py` (7 new passing tests) since 1B is a prerequisite slice with no target test able to move. Full suite: 41 passed (24 pre-existing + 10 Slice 1A + 7 Slice 1B), 15 xfailed (unchanged); `ruff check src tests` clean. Slice 1B marked COMPLETE; no further slice authorized. |
| 2026-09-12 | Slice 1C implemented: added `src/reed/composition/flow/flow_node.py` (`FlowNode` -- flow-local node participation holding a `DomainNodeDefinition`, exposing consumed/produced artifact descriptors and an optional `NodeContext` descriptor via delegation, and storing `trigger_policy`/`on_output`). `trigger_policy` is deliberately typed against the existing `PropagationPolicy` enum, not a new `TriggerPolicy` type (Priority 10/Slice 1E was explicitly not absorbed); no `DependencyRegistry` migration (Priority 8/Slice 1D) or `Flow.add(...)` wiring (Slice 1F) was performed either. No separate flow-local identity field was introduced (non-goals.md, "Multiple Registrations of the Same Node Definition" -- undecided, out of scope); the `FlowNode` instance itself is the flow-local reference. File is additive: no existing production file was modified. Added `tests/test_slice_1c_flow_node.py` (7 new passing tests) since nothing can reach `FlowNode` publicly until Slice 1F. Full suite: 48 passed (24 pre-existing + 10 Slice 1A + 7 Slice 1B + 7 Slice 1C), 15 xfailed (unchanged); `ruff check src tests` clean. Slice 1C marked COMPLETE; no further slice authorized. |
| 2026-09-12 | Slice 1D implemented: added `src/reed/composition/flow/artifact_dependency_graph.py` (`ArtifactDependencyGraph`/`DuplicateArtifactProducerError`/`SelfFlowError` -- `DependencyRegistry` migrated to `FlowNode`/domain-artifact-type vocabulary; preserves unique-producer validation and adds self-flow validation at registration time as a second, composition-level enforcement of architectural_invariants.md #11). The old `Role`/Parcel-keyed `DependencyRegistry` (`dependency_registry.py`) was confirmed byte-for-byte untouched; its 2 regression tests remain green. No `PropagationPolicy`/`TriggerPolicy` work (Priority 10/Slice 1E) or `Flow.add(...)` wiring (Slice 1F) was performed -- the new graph is standalone and not called from anywhere yet. File is additive: no existing production file was modified. Added `tests/test_slice_1d_artifact_dependency_graph.py` (8 new passing tests) since this graph is not wired into any Flow-composition entry point until Slice 1F. Full suite: 56 passed (24 pre-existing + 10 Slice 1A + 7 Slice 1B + 7 Slice 1C + 8 Slice 1D), 15 xfailed (unchanged); `ruff check src tests` clean. Slice 1D marked COMPLETE; no further slice authorized. |
| 2026-09-12 | Slice 1E implemented: added `src/reed/composition/flow/trigger_policy.py` (`TriggerPolicy` enum -- `ANY_INPUT_CHANGED`/`ALL_INPUTS_CHANGED`/`MANUAL` -- plus `from_propagation_policy(...)`, a pure old-to-new value mapping not wired into any execution path). Modified `src/reed/composition/flow/flow_node.py` (a Slice 1C target-architecture file, not legacy-protected): `FlowNode.trigger_policy` retyped from `PropagationPolicy` to `TriggerPolicy`, default changed to `TriggerPolicy.ALL_INPUTS_CHANGED`, completing the ownership relocation `refactor_priority_order.md`'s "FlowNode / DependencyRegistry ordering (resolved)" note assigned to this slice. The old `PropagationPolicy`/`NodeDefinition`/`Node` (`propagation_policy.py`, `node_definition.py`, `node.py`) were confirmed byte-for-byte untouched; their execution-eligibility match-statement logic is unmodified and still what actually runs today. Updated `tests/test_slice_1c_flow_node.py` (a Slice 1C test file) to assert against `TriggerPolicy` instead of `PropagationPolicy`, since `FlowNode`'s field type legitimately changed in this slice -- all 7 tests still pass. Added `tests/test_slice_1e_trigger_policy.py` (9 new passing tests) since `TriggerPolicy` has no consumer reachable publicly until Slice 1F. No execution logic was updated to read `trigger_policy` (Priority 10 recommended-work item 4 deferred to Milestone 2/`NodeRuntime`), no `Flow.add(...)` wiring, no callback dispatch. Full suite: 65 passed (24 pre-existing + 10 Slice 1A + 7 Slice 1B + 7 Slice 1C + 8 Slice 1D + 9 Slice 1E), 15 xfailed (unchanged); `ruff check src tests` clean. Slice 1E marked COMPLETE; no further slice authorized. |
| 2026-09-12 | Slice 1F implemented: `Flow.add(...)` (`src/reed/composition/flow/flow_composition.py`, new `reed.Flow`) wires `NodeDefinition -> Flow.add(...) -> FlowNode -> ArtifactDependencyGraph`; top-level `src/reed/flow.py` re-exports `FlowNode`; `src/reed/__init__.py` additively exports `Flow`/`TriggerPolicy`/`NodeContext`. `trigger_policy`/`on_output` are keyword-only and stored as inert Flow-local metadata; positional configuration is rejected; the new `Flow` has no `run()` method, so the six Milestone-2 target tests continue to fail (`AttributeError`) without any special-casing. A real Milestone-1 gap was found and fixed during verification: `DomainNodeSignatureParser`/`DomainNodeDescriptionBuilder` (Slice 1A/1B) now accept an optional, default-`None` `extra_globalns`, populated from `Flow.add(...)`'s immediate caller frame, so a node function's annotations can reference a name (e.g. `NodeContext`) imported in the caller's local scope rather than only at module level -- this was not Milestone-2 runtime behavior, so it was fixed rather than reported as a stop-and-report mismatch. `tests/test_target_architecture_contract.py`'s module-level blanket `xfail` was replaced with six precise per-test `xfail` markers (one per remaining Milestone-2 test, each citing its Milestone-2 slice); no assertion was changed. Verified: `tests/test_target_architecture_contract.py` -- 9 passed, 6 xfailed, zero XPASS; full suite -- 74 passed (65 pre-existing + 9 newly-passing target contract tests), 6 xfailed; `ruff check src tests` clean; blast radius on existing tracked files limited to `src/reed/__init__.py` and `tests/test_target_architecture_contract.py`. Milestone 1 (Slices 1A-1F) is now COMPLETE. Slice 1F marked COMPLETE; no further slice authorized (Milestone 2 / Slice 2A not begun). |
| 2026-09-12 | Slice 1F follow-up (maintenance, not a new architectural slice): reviewed whether `Flow.add(...)`'s caller-frame annotation-resolution fallback was minimal and robust. Finding: it worked, violated no architectural invariant or non-goal, but was not minimal -- it captured the caller's frame unconditionally on every `add()` call rather than only when needed, and its comment understated how narrowly it actually generalizes (only when the caller of `add(...)` is also the function's definer, which the target-contract tests happen to satisfy but arbitrary wrapper/factory code would not). Refined `Flow.add(...)` (`flow_composition.py`) to attempt normal `get_type_hints` resolution first and inspect `sys._getframe(1)` / retry once, with the caller's locals merged in, only if that first attempt raises `NameError`; `domain_signature.py` and `domain_node_description.py` were not modified (their `extra_globalns` parameter already supported exactly this merge). Documented the known limitation in `domain_signature.py`'s module docstring for future maintainers of composition/signature resolution; no new architectural decision was created. Verified behaviorally (an instrumented reproduction script, not committed) that the retry path fires only for the local-scope-import case and not for ordinary module-level-resolvable annotations. Full verification re-run: target contract -- 9 passed, 6 xfailed, zero XPASS; full suite -- 74 passed, 6 xfailed (unchanged from before this follow-up); `ruff check src tests` clean. Blast radius: `src/reed/composition/flow/flow_composition.py` and `src/reed/composition/node/domain_signature.py` only (both untracked Slice 1F files; no other file touched). Slice 1F remains COMPLETE; no further slice authorized. |
| 2026-09-12 | Milestone 1 (Slices 1A-1F) committed as `4fb0a76` ("Milestone 1 concluded."); this is now the validated baseline for Milestone 2 (per this task's own instruction). Slice 2A implemented on top of it: `src/reed/execution/run.py` (new) adds the minimal `Run` class (a back-reference to its originating `Flow`, nothing else); `Flow.run()` (`flow_composition.py`) returns a new `Run` per call and adds no state to `Flow`. `Flow != Run` (architectural_invariants.md #4, #6) is now real, verified structurally (a test snapshots `vars(flow)` before/after repeated `run()` calls and asserts identity-equality throughout). `reed/__init__.py` additively exports `Run`. No target architecture contract test moved -- correctly predicted in advance by reading all six remaining xfail bodies and confirmed after (`tests/test_target_architecture_contract.py`: 9 passed, 6 xfailed, zero XPASS, unchanged). `tests/test_current_regression_flow_runtime.py` (the named regression guard for this slice) reconfirmed green (3 passed). Added `tests/test_slice_2a_flow_run.py` (9 new passing tests). **Reported, not silently decided:** `docs/refactor_priority_order.md`'s Slice 2A row also suggests a `.repository` accessor on `Run`, backed by `Depot`; inspection showed `Depot.__init__` requires a live `Bus` and the full legacy transportation/lifecycle stack, disproportionate to this slice's boundary-only scope and in tension with the ADR's and non-goals' incremental, anti-speculative guidance -- deliberately deferred, recorded under "Open Architectural Questions", and pinned by a negative test. No later Milestone 2 behavior (`NodeRuntime`, `ArtifactRecord` wrap/unwrap, `ctx.memory`/`ctx.last_output`, `NodeExecution`, commit semantics, `on_output` dispatch, callback failure handling, stateful firing serialization, `ArtifactRepository` migration) was introduced. Full suite: 83 passed (74 pre-existing + 9 new), 6 xfailed (unchanged); `ruff check src tests` clean; blast radius (now git-diff-verifiable against the committed baseline) limited to `src/reed/__init__.py` and `src/reed/composition/flow/flow_composition.py` among tracked files, plus two new untracked files. Slice 2A marked COMPLETE; no further slice authorized (Slice 2B not begun). |
| 2026-09-12 | Pre-2B Review ("Run Repository Ownership", read-only, no code or documentation modified): re-inspected `docs/refactor_priority_order.md`'s Milestone 2 table and its prose ("`Run` gets a `.repository` accessor from this point on [Slice 2A] ... it does not require the `Depot` -> `ArtifactRepository` rename to already be done"), `docs/non-goals.md` in full, `src/reed/synchronization/logistics.py`, `src/reed/transportation/bus.py`, and `src/reed/composition/node/node.py`. Found that Slice 2A's `.repository` deferral rested on two mistaken premises: constructing a `Bus`+`Depot` pair is the same trivial, already-used, regression-tested two-line pattern `Logistics.__init__` already relies on today (not "the full legacy transportation/lifecycle stack"), and `docs/non-goals.md`'s "Repository Exposure"/"Execution Infrastructure Exposure" sections are scoped explicitly to `NodeContext`, not to `Run`. Concluded the ADRs already determine the answer (`Run` should own repository storage, concretely from Slice 2A per priority-order's uncontradicted guidance) and recommended a Slice 2A follow-up rather than a new architectural decision. Reported to the user; Slice 2B not begun. |
| 2026-09-12 | Slice 2A follow-up (maintenance correction, not a new architectural slice): corrected the `.repository` deferral identified by the Pre-2B Review. `src/reed/execution/run.py`: `Run.__init__` now constructs its own `Bus` + `Depot` pair (`Bus.create()`, `Depot(bus=bus)`) and exposes it via a new `repository` property; each `Run` therefore owns a distinct repository instance (verified: two `Run`s created from the same `Flow` have different `Depot.identity`, since each constructs its own `Bus`). `src/reed/composition/flow/flow_composition.py`: module/class docstrings corrected to describe the repository ownership rather than its deferral; `Flow.run()` itself unchanged (`return Run(self)`). `Depot`, `Bus`, and `Flow`'s own instance state were not modified -- `Flow` still owns no Run-specific state, repository included (verified by test). `tests/test_slice_2a_flow_run.py` updated in place: the negative test `test_run_has_no_repository_accessor_yet` was replaced with six positive tests (accessor exists; backed by `Depot`; each `Run` owns a distinct repository instance; two `Run`s from the same `Flow` do not share repository identity; `Flow` does not own the repository; repeated `Flow.run()` calls remain independent with distinct repositories) -- file now has 14 tests, all passing (was 9). No `NodeRuntime`, `ArtifactRecord`, domain-facing `get`/`set` API, commit semantics, or execution behavior was introduced; `Depot` was not renamed; no adapter/protocol/factory/manager layer was added. The "Open Architectural Questions" entry for `Run.repository` is resolved and removed. Verified: focused Slice 2A tests -- 14 passed; target architecture contract -- 9 passed, 6 xfailed, zero XPASS (unchanged, as predicted -- this follow-up moves no target test); full suite -- 88 passed (83 pre-existing + 5 net new focused tests), 6 xfailed (unchanged); `ruff check src tests` -- all checks passed. Blast radius: `src/reed/execution/run.py`, `src/reed/composition/flow/flow_composition.py` (docstrings only), `tests/test_slice_2a_flow_run.py`, `docs/refactor_state.md` -- no other file touched. Slice 2A remains COMPLETE, now with the repository-ownership question resolved rather than deferred; no further slice authorized (Slice 2B not begun). |
| 2026-09-12 | Slice 2B implemented: `src/reed/execution/node_runtime.py` (new) adds the minimal `NodeRuntime` class (a back-reference to its owning `Run` and to the `FlowNode` it materializes, nothing else). `Run.node_runtime(node)` added (`run.py`): resolves the original node callable to its `FlowNode` via a new read-only `Flow.flow_nodes` property (`flow_composition.py`), then get-or-creates and memoizes a `NodeRuntime` per `Run` in a new `self._node_runtimes` dict. The access shape (`run.node_runtime(<node function>)`) follows `tests/test_target_architecture_contract.py::test_run_instances_isolate_node_memory`'s existing usage rather than inventing a new API. `FlowNode != NodeRuntime` (architectural_invariants.md #2) is now real, verified structurally (a test confirms `FlowNode`'s own field values are unchanged, via `dataclasses.fields`, after `NodeRuntime` lookups) and by identity (two `Run`s from the same `Flow` never share a `NodeRuntime`; repeated lookups on one `Run` return the same instance). `Flow` acquired no `NodeRuntime` ownership (verified via `vars(flow)` and explicit `hasattr` checks, same technique as Slice 2A). Added `tests/test_slice_2b_node_runtime.py` (9 new passing tests). `tests/test_slice_2a_flow_run.py` updated in place: `test_run_has_no_execution_capability_yet` renamed to `test_run_has_no_publish_capability_yet` and narrowed to drop its now-stale `not hasattr(run, "node_runtime")` assertion, since `node_runtime` legitimately exists as of this slice (Test Integrity Rule correction, same precedent as Slice 1E's and the Slice 2A follow-up's test updates) -- file unchanged in test count (14), all still passing. No target architecture contract test moved -- correctly predicted in advance (the one xfail test that reaches `NodeRuntime`, `test_run_instances_isolate_node_memory`, also needs `ctx.memory` and `.publish(...)`, both later slices) and confirmed after (`tests/test_target_architecture_contract.py`: 9 passed, 6 xfailed, zero XPASS, unchanged). `tests/test_current_regression_flow_runtime.py` reconfirmed green (3 passed). No argument construction, unwrapping, `NodeContext` injection, `NodeMemory`, `NodeExecution`, execution, commit, `on_output` dispatch, callback handling, stateful-firing serialization, or repository wiring into `NodeRuntime` was introduced. Full suite: 97 passed (88 pre-existing + 9 new), 6 xfailed (unchanged); `ruff check src tests` clean; blast radius limited to `src/reed/execution/node_runtime.py` (new), `src/reed/execution/run.py` and `src/reed/composition/flow/flow_composition.py` (both modified -- the latter's tracked-file diff against the `4fb0a76` baseline grew from 65 to 94 inserted lines, the ~29-line delta being this slice's `flow_nodes` property and docstring updates), `tests/test_slice_2b_node_runtime.py` (new), and `tests/test_slice_2a_flow_run.py` (one narrowing edit) -- nothing else changed, and `src/reed/__init__.py` was not touched (`NodeRuntime` is not re-exported at the top level; reached only via `run.node_runtime(...)`). Slice 2B marked COMPLETE; no further slice authorized (Slice 2C not begun). |
| 2026-09-12 | Slice 2C implemented: `src/reed/execution/artifact_record.py` (new) adds `ArtifactVersion`/`ArtifactProvenance`/`ArtifactRecord[DomainType]`, mirroring `ParcelVersion`/`ParcelProvenance`'s exact versioning/provenance mechanics via composition (`ArtifactRecord.value` is a plain domain instance, not a `Parcel` subclass), adapted so `ArtifactProvenance.producer` references a `NodeRuntime` and `dependencies` is keyed by domain type. `NodeRuntime.unwrap(record)` added (`node_runtime.py`): a pure `record.value` passthrough, the only `NodeRuntime` integration performed. `Domain Value != ArtifactRecord` (architectural_invariants.md #7) is now real. Deliberately did not rename `ParcelVersion`/`ParcelProvenance`/`Parcel` in place, per this slice's own task instruction (narrower than `docs/refactor_priority_order.md` Priority 7 item 3's literal phrasing), consistent with the Slice 1D/1E precedent; legacy `Parcel`/`Depot`/`Outpost` confirmed byte-for-byte untouched (`git diff --stat -- src/reed/synchronization/` empty). **Major reported finding:** `Depot.set_parcel(...)` hard-rejects any non-`Parcel` value, so `run.repository` structurally cannot hold an `ArtifactRecord` yet; resolved as non-blocking for this slice specifically (nothing commits an `ArtifactRecord` in 2C, so nothing needs to store one), and recorded as a new Open Architectural Question for Slice 2E/3A rather than forced or silently worked around. Added `tests/test_slice_2c_artifact_record.py` (12 new passing tests), including a dedicated test pinning `Depot`'s continued rejection of a constructed `ArtifactRecord`. No target architecture contract test moved -- correctly predicted in advance (no remaining xfail test references `ArtifactRecord`, and `run.repository.get(...)` still does not exist) and confirmed after (`tests/test_target_architecture_contract.py`: 9 passed, 6 xfailed, zero XPASS, unchanged). `tests/test_current_regression_artifacts_repository.py` reconfirmed green (6 passed). No `NodeContext` runtime state, `ctx.memory`/`ctx.last_output`, `NodeMemory`, `NodeExecution`, node-function firing, transactional commit, `.publish(...)`, `on_output` dispatch, callback handling, stateful-firing serialization, or `ArtifactRepository` rename was introduced; `Run`/`FlowNode`/`Flow` (`run.py`/`flow_composition.py`) confirmed unchanged by this slice via sha256 match against their post-2B content. Full suite: 109 passed (97 pre-existing + 12 new), 6 xfailed (unchanged); `ruff check src tests` clean; blast radius limited to `src/reed/execution/artifact_record.py` (new), `src/reed/execution/node_runtime.py` (modified -- one method added), `tests/test_slice_2c_artifact_record.py` (new) -- nothing else changed. Slice 2C marked COMPLETE; no further slice authorized (Slice 2D not begun). |
| 2026-09-12 | Slice 2D implemented: `src/reed/composition/node/node_context.py` (modified) gives `NodeContext[MemoryType, OutputType]` (Slice 1A's empty `__slots__ = ()` shell) real `ctx.memory`/`ctx.last_output` properties over two plain values it is constructed with -- no back-reference to `NodeRuntime`/`Run`/`Flow`/repository/bus at all, a deliberately stronger reading of `docs/non-goals.md`'s "NodeContext Scope". `src/reed/execution/node_runtime.py` (modified) gained `.memory` (lazily instantiated from the FlowNode's declared `MemoryType` via zero-argument construction -- derived from `docs/refactor_priority_order.md` Priority 5's "instantiate memory from MemoryType", not guessed -- and memoized per `NodeRuntime`), `.last_output` (always `None`; no commit exists yet), and `.context` (a fresh `NodeContext` snapshot built from both); all three raise `AttributeError` for a node declaring no `NodeContext` parameter, so `hasattr(...)` correctly reports `False` for such a node. `NodeMemory` scope = `Run x NodeRuntime` (architectural_invariants.md #14, #16) falls out of Slice 2B's existing `NodeRuntime` isolation plus this slice's per-instance memoization -- verified directly (two `Run`s from the same `Flow`, same node, have independent memory); `FlowNode`/`Flow` store no memory (verified structurally). Added `tests/test_slice_2d_node_context.py` (13 new passing tests). Two prior slices' negative tests were corrected in place (Test Integrity Rule, same precedent as Slices 1E/2A-follow-up/2B): `tests/test_slice_2b_node_runtime.py::test_node_runtime_has_no_execution_capability_yet` renamed/narrowed to keep only its still-true `repository`/`execute` assertions; `tests/test_slice_1a_domain_signature_parsing.py::test_node_context_shell_has_no_runtime_behavior` renamed to `test_node_context_shell_is_generic_and_detectable` with its now-false `NodeContext.__slots__ == ()` assertion removed -- both files' full suites re-confirmed passing (9/9, 10/10). No target architecture contract test moved -- correctly predicted in advance (both remaining relevant xfail tests require `run.publish(...)`, Slice 2E) and confirmed after (`tests/test_target_architecture_contract.py`: 9 passed, 6 xfailed, zero XPASS, unchanged). `tests/test_current_regression_flow_runtime.py` reconfirmed green (3 passed). The Slice 2C repository-storage mismatch (Open Architectural Questions) was left completely untouched, as instructed -- `run.repository`/`Depot` were not read from or written to by anything in this slice. No `NodeExecution`, node-function firing, argument construction, `ArtifactRecord` commit, repository commit semantics, transactional firing, `TriggerPolicy` execution eligibility, `on_output` dispatch, async callbacks, callback failure behavior, stateful-firing serialization, or `Depot` -> `ArtifactRepository` migration was introduced. Full suite: 122 passed (109 pre-existing + 13 new), 6 xfailed (unchanged); `ruff check src tests` clean; blast radius limited to `src/reed/composition/node/node_context.py` and `src/reed/execution/node_runtime.py` (modified), `tests/test_slice_2b_node_runtime.py` and `tests/test_slice_1a_domain_signature_parsing.py` (one stale negative test corrected each), and `tests/test_slice_2d_node_context.py` (new) -- `run.py`, `artifact_record.py`, `flow_composition.py`, and everything under `src/reed/synchronization/` confirmed untouched. Slice 2D marked COMPLETE; no further slice authorized (Slice 2E not begun). |
| 2026-09-12 | Reed Agentic Refactor Workflow bootstrap: Slices 2A-2D (previously completed but uncommitted) committed as a single bootstrap checkpoint (`1113706`, on top of `4fb0a76`) after independently re-verifying the actual repository (122 passed, 6 xfailed; ruff clean) against this document's own Slice 2D record -- no file attributed to any slice was reconstructed or guessed, only committed. A `reed-architect` invocation was then run for Slice 2E under the autonomous workflow; it correctly escalated (`HUMAN_DECISION_REQUIRED`) on the Open Architectural Question above rather than guessing among its recorded alternatives. A human then made and this document now records the Slice 2E storage decision (see `docs/parcel_boundary_decision.md`'s addendum, and this document's updated "Open Architectural Questions" and "Next Recommended Slice" sections). No production code changed as part of this log entry; Slice 2E itself has not yet been implemented. |
| 2026-09-12 | Slice 2E implemented (autonomous workflow, first fully autonomous slice under the "Decision autonomy within a slice" policy): `Run.publish(domain_value)` added (`run.py`) -- single-`FlowNode`/single-type-match dispatch, raising `ValueError` on zero or on multiple candidate matches (a stop_condition pinned by two dedicated tests); resolves node arguments (including a constructed `NodeContext` when the node declares one), invokes the node function, then wraps and commits the result via `NodeRuntime`. `NodeRuntime.wrap(domain_value) -> ArtifactRecord` and `NodeRuntime.commit(record)` added (`node_runtime.py`): `wrap` advances provenance with `producer=self`; `commit` writes into `run.repository` and updates `NodeRuntime._last_output`. `Depot` (`synchronization/depot.py`) gained a wholly separate, additive `_artifact_records: Dict[type, ArtifactRecord]` store plus `set_artifact_record`/`get_artifact_record`, keyed by `type(record.value)` -- per the human-accepted Slice 2E storage decision (`docs/parcel_boundary_decision.md`'s addendum): the existing `_storage`/`set_parcel`/`get_parcel`/bus-message path is completely untouched; no widening of the Parcel API; the `Depot -> ArtifactRepository` rename remains Slice 3A's alone. `NodeRuntime.last_output` is a synchronized local view of the latest successfully committed domain value, not itself authoritative -- the committed `ArtifactRecord` in `Depot` is. Two target-architecture-contract tests newly pass: `test_run_instances_isolate_node_memory`, `test_last_output_exposes_latest_committed_domain_value` (their `xfail(strict=True)` markers removed; no assertion touched). Added `tests/test_slice_2e_node_execution.py` (7 new passing tests: publish/wrap/commit; storage independence from Parcel storage; `last_output` wiring; `NodeContext` injection; both multi-/zero-match `ValueError` guards). Three prior slices' stale negative assertions were corrected in place under the Test Integrity Rule, following the established Slice 2B/2D precedent and this slice's own "decision autonomy" authorization (each a single named-function, single-assertion flip/removal, pre-authorized in the SliceContract's `scope.allowed_test_corrections`): `tests/test_slice_2a_flow_run.py::test_run_has_no_publish_capability_yet` renamed to `test_run_publish_capability_was_introduced` (`not hasattr(run, "publish")` flipped to `hasattr(...)`); `tests/test_slice_2c_artifact_record.py::test_node_runtime_has_no_wrap_capability_yet` renamed to `test_node_runtime_wrap_capability_was_introduced` (same flip for `.wrap`); `tests/test_slice_2d_node_context.py::test_no_execution_commit_or_repository_capability_was_introduced` renamed to `test_no_execute_fire_or_context_commit_wrap_unwrap_capability_was_introduced`, with only its now-false `publish`/`commit` lines removed -- its still-true `execute`/`fire`/`ctx.commit`/`ctx.wrap`/`ctx.unwrap` assertions (none introduced by this slice) were kept. No `on_output` dispatch, async callbacks, callback-failure handling, stateful-firing serialization, `TriggerPolicy` execution eligibility, or `Depot -> ArtifactRepository` migration was introduced. Full suite: 131 passed (122 pre-existing + 7 new + 2 newly-passing target-contract tests), 4 xfailed (down from 6); `ruff check src tests` clean. This slice went through one FIX iteration: the Reviewer's first pass correctly flagged that `implementation_report.0.yaml` did not disclose four unrelated `.claude/` files (`.claude/agents/reed-architect.md`, `.claude/agents/reed-implementer.md`, `.claude/agents/reed-reviewer.md`, `.claude/skills/reed-refactor/SKILL.md`) that changed during the run's window; these were orchestrator-level "Decision autonomy within a slice" policy updates made directly by the orchestrating session, unrelated to Slice 2E's own production/test diff -- `implementation_report.1.yaml` disclosed and explained them (no code changed), and the Reviewer's second pass independently re-verified this and returned PASS. Blast radius (tracked production/test files only): `src/reed/execution/run.py`, `src/reed/execution/node_runtime.py`, `src/reed/synchronization/depot.py`, `tests/test_slice_2a_flow_run.py`, `tests/test_slice_2c_artifact_record.py`, `tests/test_slice_2d_node_context.py`, `tests/test_target_architecture_contract.py` (modified), `tests/test_slice_2e_node_execution.py` (new), plus this `docs/refactor_state.md` update. Slice 2E marked COMPLETE and checkpoint-committed; the autonomous workflow proceeds to Slice 2F without human approval, per the current autonomous-execution policy. |
| 2026-09-12 | Slice 2F implemented (autonomous, no human intervention -- resolved under the "Decision autonomy within a slice" policy): `Run.publish(...)` (`run.py`) gained `on_output` dispatch strictly after `NodeRuntime.commit(record)` succeeds -- sync `on_output` callables invoked inline; async callables' coroutines queued and drained only via an explicit new `Run.wait_for_callbacks()` (one bounded `asyncio.run(asyncio.gather(..., return_exceptions=True))` call; no standing event loop, background thread, or other always-on scheduling infrastructure was introduced, per non-goals.md). Callback failures (sync or async) are isolated onto a new `run.callback_failures` list -- they never roll back, block, or otherwise affect the already-committed `ArtifactRecord`/repository state, and never prevent other callbacks or subsequent `publish()` calls from proceeding (architectural_invariants.md #21-23). `Depot.get(domain_type)` added (`depot.py`) as a thin one-line delegating alias to the existing `get_artifact_record` -- not a rename, not a widening of the Parcel API; the `Depot -> ArtifactRepository` migration remains untouched and deferred to Slice 3A. Three target-architecture-contract tests newly pass: `test_on_output_runs_after_commit_and_receives_domain_value`, `test_async_on_output_is_supported_after_commit`, `test_callback_failure_does_not_undo_committed_output` (only their `xfail(strict=True)` markers removed; no assertion body changed). Added `tests/test_slice_2f_on_output_dispatch.py` (7 new passing tests: no-callback path, sync inline dispatch, async queuing/draining, sync and async failure isolation, `wait_for_callbacks()` no-op, `Depot.get` alias). No `TriggerPolicy` consultation, stateful-firing serialization/locking (Slice 2G's own scope), composition-layer file, or transportation/Parcel-internal file was touched -- confirmed via git diff and this run's own `baseline.py diff`, which matched the ImplementationReport's declared blast radius exactly with nothing undisclosed. Full suite: 141 passed (131 pre-existing + 7 new + 3 newly-passing target-contract tests), 1 xfailed (down from 4 -- only `test_stateful_node_runtime_firings_are_serialized`, Slice 2G's, remains); `ruff check src tests` clean. Reviewed and independently re-verified by an isolated Reviewer subagent in a single pass (PASS, no FIX iteration needed). Blast radius (tracked production/test files only): `src/reed/execution/run.py`, `src/reed/synchronization/depot.py`, `tests/test_target_architecture_contract.py` (modified), `tests/test_slice_2f_on_output_dispatch.py` (new), plus this `docs/refactor_state.md` update. Slice 2F marked COMPLETE and checkpoint-committed; the autonomous workflow proceeds to Slice 2G (the final Milestone 2 slice: stateful `NodeRuntime` firing serialization) without human approval, per the current autonomous-execution policy. |
| 2026-09-12 | Slice 2G implemented (autonomous, single Reviewer pass, no FIX iteration) -- **Milestone 2 (Slices 2A-2G) is now fully COMPLETE**: `NodeRuntime.firing_lock` (`node_runtime.py`) added -- a lazily-created, memoized `threading.Lock`, gated on the same state-awareness signal Slice 2D established (`flow_node.context is not None`); a stateless `NodeRuntime` never constructs a lock. `Run.publish(...)` (`run.py`) now acquires this lock immediately before the node-function call and releases it in a `finally` covering the call, wrap, and commit; `Run.publish_many(values)` added as a thin sequential loop over `publish(...)`, introducing no new scheduler/executor/event-loop/thread-pool infrastructure (non-goals.md, "Advanced Parallel Scheduling"). The target test `test_stateful_node_runtime_firings_are_serialized` newly passes (only its `xfail(strict=True)` marker removed; assertion untouched). Added `tests/test_slice_2g_stateful_serialization.py` (4 new passing tests), including a genuine multi-thread concurrency proof (real background threads, a deliberately slow node function, independently tracked `max_active`) demonstrating the lock actually prevents overlapping firings of the same stateful `NodeRuntime` -- confirmed by the Reviewer to be a real proof, not a test that would pass without the fix. No `Depot`/`ArtifactRepository`, `TriggerPolicy` consultation, transportation/**, or 2A-2F test file was touched. **`tests/test_target_architecture_contract.py` now has 15 passed, 0 xfailed, 0 xpassed** -- every Milestone 1 and Milestone 2 target-architecture test named in `docs/refactor_priority_order.md` now passes unconditionally, with zero remaining xfail markers in that file (independently confirmed by the Reviewer via full-file grep). Full suite: 146 passed (141 pre-existing + 4 new + 1 newly-passing target-contract test), 0 xfailed; `ruff check src tests` clean. Blast radius (tracked production/test files only): `src/reed/execution/node_runtime.py`, `src/reed/execution/run.py`, `tests/test_target_architecture_contract.py` (modified), `tests/test_slice_2g_stateful_serialization.py` (new), plus this `docs/refactor_state.md` update. Slice 2G marked COMPLETE and checkpoint-committed. Per `docs/roadmap.md`'s "Resolve issue #4 enough to stabilize the public Flow composition API used by downstream projects" and `docs/flow_composition_implementation_basis.md`'s target public API list (typed domain Nodes, explicit Flow composition, optional NodeContext, per-node trigger policy, post-commit output callbacks) -- all now real and fully test-verified -- Milestone 2's completion satisfies Issue 4's planned scope. Milestone 3 ("Infrastructure Alignment": the `Depot -> ArtifactRepository` rename and Priorities 16-24) is explicitly cross-cutting internal vocabulary work that `docs/refactor_priority_order.md` itself states "no target test depends on ... except indirectly" -- it is not part of Issue 4's target-contract scope. This entry records that finding for the Reviewer's final Issue-4-completion verification pass. |
| 2026-09-12 | **Issue #4 REOPENED by the project owner; the `ISSUE_4_COMPLETE` marker recorded above (after Slice 2G) is superseded.** Passing the target-architecture-contract suite was necessary but not sufficient: Issue #4 replaces foundational execution architecture, and completion requires Reed to work end-to-end as a real automatic dataflow system, not merely that the new abstractions exist. A pre-Issue-4 foundational behavior audit was performed (`docs/pre_issue4_behavior_audit.md`, repository authority for this finding): the legacy `@flow`/`@node` implementation (commit `fd14a37`, immediately pre-Issue-4) had a complete, working, automatic, message-driven, multi-hop, fan-out- and join-capable propagation engine (`Outpost`/`Depot`/`Bus` dirty-flag broadcast, `PropagationPolicy`-gated firing); the current implementation through Slice 2G replaced this with manual, single-hop, single-node `Run.publish(...)` calls the caller must chain by hand, with `Run.publish` explicitly rejecting any FlowNode with more than one consumed type (no joins) or more than one matching consumer (no fan-out), and `TriggerPolicy` existing only as inert composition-time metadata. No accepted architectural decision authorizes dropping this capability. The new terminal condition for Issue #4 (superseding the prior one) requires: Milestones 1-2 remain correct; automatic multi-hop propagation (including fan-out and multi-input joins) works; `TriggerPolicy` actually gates execution; Milestone 3 (Infrastructure Alignment) is complete; the pre-Issue-4 behavior audit's regressed capabilities are restored/re-expressed through the new architecture; the public API hides internal orchestration; regression, target-contract, and new propagation/integration tests are all green; a runnable quality-gate example (`examples/`) and an automated end-to-end acceptance test derived from it both pass; and a fresh, independent final-audit Reviewer signs off. Slices continue autonomously (Architect determines exact slice boundaries from repository authority; not limited to the previously documented roadmap) starting from Slice 2H (automatic propagation core). |
