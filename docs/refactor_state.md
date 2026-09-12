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
- Last known base commit: `54f20ce87be8574a1bb6df1973797b1e91887aa9`
- Working tree: dirty
- Production code modified: yes (Slices 1A-1D were additive only; Slice 1E retyped one field on a Slice 1C file; Slice 1F added two new files and additionally made small, additive modifications to five existing Slice 1A-1E files plus `src/reed/__init__.py` -- see "Slice 1F record" below for the exact list)
- Documentation modified: yes
- Tests modified: yes

Current uncommitted work:

- `docs/implementation_refactor_assessment.md`
- `docs/non-goals.md`
- `docs/refactor_guide.md`
- `docs/refactor_agent_protocol.md`
- `docs/refactor_priority_order.md`
- `docs/refactor_state.md`
- `docs/reed_refactor_harness.md`
- `tests/test_current_regression_artifacts_repository.py`
- `tests/test_current_regression_flow_runtime.py`
- `tests/test_current_regression_node_description.py`
- `tests/test_target_architecture_contract.py`
- `tests/test_slice_1a_domain_signature_parsing.py` (new -- Slice 1A)
- `src/reed/composition/node/domain_signature.py` (new -- Slice 1A)
- `src/reed/composition/node/node_context.py` (new -- Slice 1A)
- `tests/test_slice_1b_domain_node_description.py` (new -- Slice 1B)
- `src/reed/composition/node/artifact_descriptor.py` (new -- Slice 1B)
- `src/reed/composition/node/domain_node_description.py` (new -- Slice 1B)
- `tests/test_slice_1c_flow_node.py` (new -- Slice 1C)
- `src/reed/composition/flow/flow_node.py` (new -- Slice 1C)
- `tests/test_slice_1d_artifact_dependency_graph.py` (new -- Slice 1D)
- `src/reed/composition/flow/artifact_dependency_graph.py` (new -- Slice 1D)
- `tests/test_slice_1e_trigger_policy.py` (new -- Slice 1E)
- `src/reed/composition/flow/trigger_policy.py` (new -- Slice 1E; modified -- Slice 1F, docstring only)
- `src/reed/composition/node/domain_signature.py` (modified -- Slice 1F: added optional `extra_globalns` parameter)
- `src/reed/composition/node/domain_node_description.py` (modified -- Slice 1F: threads `extra_globalns` through to the parser)
- `src/reed/composition/node/node_context.py` (modified -- Slice 1F, docstring only)
- `src/reed/composition/flow/flow_node.py` (modified -- Slice 1F, docstring only)
- `src/reed/composition/flow/artifact_dependency_graph.py` (modified -- Slice 1F, docstring only)
- `src/reed/composition/flow/flow_composition.py` (new -- Slice 1F)
- `src/reed/flow.py` (new -- Slice 1F, top-level `FlowNode` re-export)
- `src/reed/__init__.py` (modified -- Slice 1F: exports `Flow`, `TriggerPolicy`, `NodeContext`)
- `AGENTS.md` (repo root, new)
- `CLAUDE.md` (repo root, new)

## Baseline Verification

Last verified: 2026-09-12

Configured command:

```bash
uv run pytest -q
```

Result (as of 2026-09-12, after Slice 1F):

```text
74 passed, 6 xfailed
```

Coverage percentage not re-measured this session (sandbox could not write
`.coverage` in the mounted working tree); this does not affect pass/fail
counts. Breakdown: 24 pre-existing regression tests (unchanged) + 10
Slice 1A focused tests + 7 Slice 1B focused tests + 7 Slice 1C focused
tests + 8 Slice 1D focused tests + 9 Slice 1E focused tests + 9
Milestone-1 target architecture contract tests newly passing via Slice
1F (`tests/test_target_architecture_contract.py`) = 74 passed; the
remaining 6 Milestone-2 target architecture contract tests stay xfail
(see "Slice-focused test commands" below).

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

Slices 1A, 1B, 1C, 1D, 1E, and 1F (Milestone 1 -- Typed Composition
Foundation) are all complete as of 2026-09-12. Milestone 1 is now fully
delivered: all nine of its target architecture contract tests pass. See
"Completed Slices" below for their results. Starting the next slice
(2A, the first Milestone 2 slice) requires a new explicit task -- see
"Next Recommended Slice" and the One-Slice Termination Rule in
`refactor_agent_protocol.md`.

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

## Completed Slices

| Slice | Commit | Tests changed | Result |
|---|---|---|---|
| 1A | (uncommitted; working tree dirty) | `tests/test_slice_1a_domain_signature_parsing.py` added (10 passing tests); all pre-existing regression and target-contract tests unchanged | Typed domain signature parsing implemented (`domain_signature.py`); minimal structural `NodeContext` shell implemented (`node_context.py`); `NodeContext` excluded from dataflow inputs; `NodeContext` output type validated against return type; self-flow rejected at signature level. No target architecture test moved (none could -- all gate on Slice 1F). See "Slice 1A record" above for full detail. |
| 1B | (uncommitted; working tree dirty) | `tests/test_slice_1b_domain_node_description.py` added (7 passing tests); all pre-existing regression, target-contract, and Slice 1A tests unchanged | `ArtifactDescriptor`/`ArtifactRole` implemented (`artifact_descriptor.py`); domain-typed `DomainNodeDescription`/`DomainNodeDefinition`/`NodeContextDescriptor`/`DomainNodeDescriptionBuilder` implemented (`domain_node_description.py`), reusing Slice 1A's signature parser for validation. No target architecture test moved (1B is a prerequisite for 1C-1F). See "Slice 1B record" above for full detail. |
| 1C | (uncommitted; working tree dirty) | `tests/test_slice_1c_flow_node.py` added (7 passing tests); all pre-existing regression, target-contract, and Slice 1A/1B tests unchanged | `FlowNode` implemented (`flow_node.py`): flow-local node participation holding a `DomainNodeDefinition`, exposing consumed/produced artifact descriptors and an optional `NodeContext` descriptor, and storing `trigger_policy` (typed against the existing `PropagationPolicy` enum) and `on_output`. No target architecture test moved (nothing reaches `FlowNode` publicly until Slice 1F). `TriggerPolicy` rename (1E) and `DependencyRegistry` migration (1D) were explicitly not absorbed. See "Slice 1C record" above for full detail. |
| 1D | (uncommitted; working tree dirty) | `tests/test_slice_1d_artifact_dependency_graph.py` added (8 passing tests); all pre-existing regression, target-contract, and Slice 1A/1B/1C tests unchanged; old `DependencyRegistry`'s 2 regression tests unaffected | `ArtifactDependencyGraph` implemented (`artifact_dependency_graph.py`): `DependencyRegistry` migrated to `FlowNode`/domain-artifact-type vocabulary, preserving unique-producer validation and adding self-flow validation at registration time. Old `DependencyRegistry` untouched (confirmed byte-identical). No target architecture test moved (not wired into any Flow-composition entry point until Slice 1F). `TriggerPolicy` migration (1E) and `Flow.add(...)` (1F) were explicitly not absorbed. See "Slice 1D record" above for full detail. |
| 1E | (uncommitted; working tree dirty) | `tests/test_slice_1e_trigger_policy.py` added (9 passing tests); `tests/test_slice_1c_flow_node.py` updated in place (7 tests, still passing, now asserting against `TriggerPolicy`); all pre-existing regression, target-contract, and Slice 1A/1B/1D tests unchanged | `TriggerPolicy` introduced (`trigger_policy.py`): target enum (`ANY_INPUT_CHANGED`/`ALL_INPUTS_CHANGED`/`MANUAL`) plus an unused-by-execution `from_propagation_policy(...)` mapping. `FlowNode.trigger_policy` (Slice 1C) retyped from `PropagationPolicy` to `TriggerPolicy`, completing the ownership relocation `refactor_priority_order.md` assigned to this slice. Old `PropagationPolicy`/`NodeDefinition`/`Node` untouched (confirmed byte-identical); their execution-eligibility logic is unmodified. No target architecture test moved (still gated on Slice 1F). Execution-logic wiring, `Flow.add(...)`, and callback dispatch were explicitly not absorbed. See "Slice 1E record" above for full detail. |
| 1F | (uncommitted; working tree dirty) | `tests/test_target_architecture_contract.py` modified in place (xfail-scope only: the module-level blanket marker removed, 9 tests now unmarked/passing, 6 re-marked `xfail` with per-test Milestone-2 reasons); no new dedicated Slice 1F test file -- the target contract file itself is the focused verification; all pre-existing regression and Slice 1A-1E tests unchanged | `Flow.add(...)` implemented (`flow_composition.py`, new `reed.Flow`), wiring `NodeDefinition -> Flow.add(...) -> FlowNode -> ArtifactDependencyGraph`; top-level `reed.flow` re-export added; `reed/__init__.py` exports `Flow`/`TriggerPolicy`/`NodeContext`. All nine Milestone-1 target architecture contract tests now pass; the six Milestone-2 tests remain `xfail` (they call `flow.run()`, which does not exist -- no special-casing needed). A real annotation-resolution gap in Slice 1A's `domain_signature.py` (local-scope `NodeContext` imports not visible to `get_type_hints`) was discovered and fixed via an additive, default-`None` `extra_globalns` parameter threaded from `Flow.add(...)`'s caller frame -- not Milestone-2 scope. See "Slice 1F record" above for full detail. |

## Target Contract Status

(Renamed from "Remaining Target Contracts" -- as of Slice 1F, nine of
the fifteen target contracts are delivered, not remaining.)

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
| Node boundary | User functions consume and produce `Parcel` subclasses. | User functions consume and produce domain values. | Preserve regression tests; target tests remain xfail until wrapping/unwrapping exists. |
| Artifact identity | Parcel subclass currently acts as dependency identity. | Domain type is the semantic artifact identity. | Introduce artifact descriptors before broad renaming. |
| Flow API | Flow is created through `@flow` and `FlowFactory`. | `Flow` is an explicit composition object with `Flow.add(...)`. | Introduce new API alongside compatibility path. |
| Flow-local participation | No explicit `FlowNode`. | `Flow.add(...)` returns `FlowNode`. | Add `FlowNode` before moving policy and callbacks. |
| Trigger policy ownership | `PropagationPolicy` lives on `NodeDefinition`. | `TriggerPolicy` belongs to `FlowNode`. | Move ownership after `FlowNode` exists. |
| Context injection | No `NodeContext` exists. | `NodeContext[MemoryType, OutputType]` is injected and excluded from input ports. | Implement in signature parsing slice. |
| Local memory | No explicit `NodeMemory` public boundary exists. | `NodeMemory` belongs to `Run x NodeRuntime`. | Introduce after `NodeContext` exists. |
| Runtime ownership | Current `Node` owns execution and `Outpost`. | `NodeRuntime` owns run-local execution for a `FlowNode`. | Migrate after `Run` and `FlowNode` exist. |
| Repository name | `Depot` stores current Parcels. | `ArtifactRepository` stores artifact records. | Rename only after `ArtifactRecord` is real. |
| Outpost role | `Outpost` is a broad synchronization component. | It should become internal to `NodeRuntime` or an adapter. | Do not rename to `NodeMemory`; postpone until ownership is clear. |

## Open Architectural Questions

None currently.

When an open question is added, it must include:

1. the blocking slice;
2. the missing decision;
3. why implementation depends on it;
4. alternatives discovered;
5. affected tests;
6. affected classes.

## Next Recommended Slice

Now that Slices 1A-1F have completed, Milestone 1 (Typed Composition
Foundation) is fully delivered -- all nine of its target contract tests
pass:

```text
Slice 2A -- Flow becomes a pure composition object; Flow.run() creates a Run
(docs/refactor_priority_order.md, Milestone 2, part of Priority 11 and 12)
```

Per `docs/refactor_priority_order.md`'s Milestone 2 table, Slice 2A gives
`Flow` a `run()` method that creates a `Run` (with `Run.repository`);
`Flow` itself remains a pure composition object and continues to own no
Run-specific execution state (architectural_invariants.md #4, #6). No
target architecture contract test is expected to move on 2A alone -- it
is a prerequisite for 2B-2G, the first of which a target test can move on
is 2E (`test_run_instances_isolate_node_memory`,
`test_last_output_exposes_latest_committed_domain_value`).

This is a recommendation, not an authorization. Starting Slice 2A still
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
