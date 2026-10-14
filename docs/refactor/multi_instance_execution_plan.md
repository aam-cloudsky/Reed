# Multiple Artifact Instances: Diagnosis, Risk Assessment, and Slice Plan

Status: proposal, not yet an accepted decision. This document is the scope
statement and slice map for the new issue "Support multiple artifact
instances and per-instance node execution" (title and description drafted
separately, not yet filed as a GitHub issue at the time of writing). It
plays the same role `docs/refactor_priority_order.md` played for issue #4,
scoped to this one issue only, since that file no longer exists as a
general-purpose document (see
`references/ingested/reed-docs-drift-issue-21-handoff.md`).

Everything below is grounded in the current `src/reed` implementation and
the current `docs/refactor/` documents, read directly for this diagnosis.
Every claim below cites the file, class, or method it comes from.

---

## 1. Diagnosis

Reed's composition layer already separates the computational graph from
its runtime materialization, one level up from where this issue needs the
same cut. This section states what already generalizes cleanly and what
does not.

### 1.1 Layer that needs no change: the type-level graph

`Flow`, `FlowNode`, `ArtifactDependencyGraph`, `TriggerPolicy`, `InputRole`,
and `ArtifactDescriptor` describe artifact types and node participations,
never artifact instances. `ArtifactDependencyGraph`
(`src/reed/composition/flow/artifact_dependency_graph.py`) enforces one
declared producer per artifact type (`DuplicateArtifactProducerError`) and
self-flow rejection at registration time, both scoped to type identity.
`TriggerPolicy` (`src/reed/composition/flow/trigger_policy.py`) is a plain
three-member enum with no notion of cardinality. None of these classes
hold a dict keyed by anything narrower than a domain type or a `FlowNode`.
A node declaration such as `def perception(state: AircraftState) ->
Observation: ...` stays exactly as written under this proposal, per the
issue's own architectural principle.

### 1.2 Layer that assumes exactly one instance per type

Four places in the execution layer hold a dict keyed by domain type or by
`FlowNode` alone, with no room for an instance dimension:

- `ArtifactRepository._artifact_records: dict[type, "ArtifactRecord"]`
  (`src/reed/synchronization/artifact_repository.py`). `set_artifact_record`
  keys strictly by `type(record.value)`. This is the repository's entire
  storage model: one committed record per domain type, full stop.
- `ArtifactProvenance.dependencies: dict[type, ArtifactVersion]`
  (`src/reed/execution/artifact_record.py`). A firing's recorded
  dependency versions are keyed by type only, so nothing today records
  which instance of a dependency a firing actually consumed. This is
  exactly where the Alignment question (correlating `AircraftState<A>`
  with `Pilot<A>`) has no representation to build on.
- `Session._node_sessions: dict[FlowNode, NodeSession]`,
  `Session._last_known_values: dict[FlowNode, dict[type, object]]`, and
  `Session._fresh_since_last_firing: dict[FlowNode, set[type]]`
  (`src/reed/execution/session.py`). One `NodeSession` per `FlowNode` per
  `Session`, one last-known-value slot per consumed type, one freshness
  set per node. `Session._is_eligible_to_fire` and `Session._record_input`
  both operate over these structures with no instance key anywhere in the
  path.
- `NodeSession.memory` (`src/reed/execution/node_session.py`) is lazily
  instantiated once and memoized for the `NodeSession`'s whole lifetime,
  matching architectural invariants 14 and 16 ("`NodeMemory` belongs to
  `Session × NodeSession`"). Both invariants are stated at the (Session,
  FlowNode) grain; supporting multiple instances means this grain needs
  an explicit decision, not a silent assumption either way.

### 1.3 Layer that assumes it and is not exercised by anything today

The observability subsystem (issues #7 and #8, milestones O1 through O8,
already complete and regression-tested) derives its own artifact identity
purely from domain type:
`Session._artifact_id(domain_type: type) -> str` (`session.py`, line
1010) is the single source `ProvenanceEvent.artifact_id`
(`src/reed/observability/provenance.py`) and
`build_provenance_graph`'s `(artifact_id, artifact_version)` grouping key
(`src/reed/observability/graph.py`) both derive from. `NodeExecutionIdentity`
(`src/reed/observability/identity.py`) carries `execution_id`, `flow_id`,
`node_id`, and `node_execution_id`, none of which distinguish
`perception<A>` from `perception<B>`. Nothing in this subsystem raises an
error under multiplicity; it would instead silently group every
instance's provenance under one undifferentiated artifact stream. This is
a correctness risk, not a crash risk, which makes it more dangerous, not
less.

### 1.4 Documentation-authority note

`docs/architectural_invariants.md` (top level) is stale: it still reads
`Run`/`NodeRuntime` and stops at invariant 26. The current, authoritative
version lives at `docs/refactor/architectural_invariants.md` (invariants
27 through 33, added for issue #22) per `CLAUDE.md`'s own folder-structure
note. `.claude/agents/reed-architect.md` already resolves this correctly
("currently physically under `docs/refactor/`"), but `.claude/skills/reed-refactor/SKILL.md`'s
own bootstrap section still cites the bare `docs/architectural_invariants.md`
path without the `docs/refactor/` prefix. This is a real, if narrow,
authority-resolution risk for a fresh Architect invocation and is called
out below (Risk R6).

---

## 2. Risk assessment

- **R1, repository identity collapse.** `ArtifactRepository`'s dict must
  gain an instance dimension without breaking every existing single-
  instance flow. The natural fix keys storage by `(type, instance_key)`
  with a stable default instance key for the existing, non-multiplicity
  path, so every current test keeps passing unchanged. High confidence
  fix, low architectural risk, moderate mechanical size (`get_artifact_record`,
  `set_artifact_record`, and every caller).
- **R2, alignment has no substrate.** `ArtifactProvenance.dependencies`
  today cannot express "this firing's `ControlCommand` dependency came
  specifically from `Pilot<A>`". This needs an explicit decision before
  Slice E (Alignment) can be implemented, not just a mechanical key
  change, since it determines how a multi-input node's per-instance
  firing resolves which upstream instance to read.
- **R3, eligibility and firing bookkeeping collapse.** Three parallel
  dicts in `Session` (`_node_sessions`, `_last_known_values`,
  `_fresh_since_last_firing`) all need the same new key dimension kept in
  lockstep. A partial migration, one dict updated and another not, is the
  most likely source of a silent correctness bug in this whole feature,
  since nothing would raise an exception, firings would simply fire for
  the wrong instance or not fire at all.
- **R4, NodeMemory scope decision.** Invariants 14 and 16 need an explicit
  ruling: does per-instance execution get one `NodeMemory` per instance,
  or one shared across all instances of a node. Reed's own aircraft
  example suggests per-instance memory is the useful default (each
  aircraft's `perception` node likely wants independent memory), but nothing
  in the current invariants decides this, and it changes `NodeContext`'s
  contract.
- **R5, observability silent corruption.** Already-complete, heavily
  tested milestones (O1 through O8) assume type-only artifact identity.
  Extending `_artifact_id` to include an instance key touches
  `ProvenanceEvent`, `NodeExecutionIdentity`, the durable CSV schemas
  (`recordings.csv`, `provenance.csv`), `replay.py`, and `graph.py`
  together. This is the single largest-blast-radius risk in the whole
  proposal and the one most likely to look finished while quietly
  producing misleading traces. Treat it as its own slice group, not a
  footnote on the execution-layer slices.
- **R6, documentation-authority drift.** `SKILL.md`'s bootstrap text still
  names the stale top-level invariants path. Before the first Architect
  invocation for this issue, this drift should be corrected in `SKILL.md`
  itself (a small, independent documentation fix, not part of any
  multi-instance slice) so a fresh Architect run does not read the wrong
  file.
- **R7, backward compatibility.** Every existing regression test
  (`tests/test_slice_2*`, `tests/test_slice_21*`, `tests/test_slice_22*`,
  all of `tests/test_observability_*`) exercises the single-instance path
  exclusively and must keep passing unmodified throughout. Every slice
  below is additive by construction, following the same pattern this
  repository already used for `InputRole` (default `TRIGGERING`) and
  `Sampled` (purely additive annotation).
- **R8, git-workflow conflict.** `SKILL.md` Section 5 has the orchestrator
  perform `git add`/`git commit` at each checkpoint. This conflicts with
  the standing rule that nothing in this session, or any subagent it
  spawns, runs a git write command. Section 5 below states the adaptation.
- **R9, fault isolation.** Already raised in the issue comment: no
  existing invariant covers what happens when one instance's firing
  raises while sibling instances are firing in the same propagation. This
  needs a decision before Slice H (Lifecycle) can be considered complete.
- **R10, cross-cutting size.** This feature touches the repository, the
  provenance model, the eligibility engine, and the observability
  subsystem. Keeping each slice small and independently reviewable
  matters more here than on a typical slice, since the failure mode of a
  too-large slice is exactly R3 and R5 above: a partial, inconsistent
  migration that passes its own narrow tests while breaking an invariant
  somewhere the slice's own tests do not look.

---

## 3. Implementation plan

Final outcome this plan works toward: `session.feed([AircraftState(id="A",
...), AircraftState(id="B", ...)])` commits distinct `ArtifactRecord`s per
instance; `Flow.add(perception)` materializes one firing per currently
known instance of its triggering input type; a node declared with
`Collection[AircraftState]` receives the currently resolved set of
instances as a collective dependency; and every existing single-instance
flow keeps working with no code change on the caller's side. Provenance
and observability correctly attribute every firing and every commit to
its instance.

The ordering below follows the same dependency discipline issue #22 used
for its own sub-slices (representation before propagation before
derived behavior): representation first (repository and record), then
propagation (eligibility and firing), then the two dependency semantics
the issue's own text distinguishes (Alignment, then Broadcasting and
Collective dependencies), then lifecycle and fault isolation, then
observability integration last, since observability is a pure consumer of
identity the earlier slices establish.

---

## 4. Scope and non-scope

**In scope:** instance identity as a first-class concept in the repository
and provenance model; per-instance firing for an ordinary per-instance
node declaration; per-instance `NodeMemory` (pending the R4 decision,
recorded explicitly rather than assumed); the two collective-dependency
questions (`Collection[T]`, Broadcasting of a singleton like `DeltaT`);
basic lifecycle (instances added, updated, or removed within a session);
fault isolation across sibling instance firings within one propagation;
and extending the observability subsystem so per-instance provenance and
traces stay correctly attributable.

**Out of scope:** concurrent or parallel execution of instance-level
firings (roadmap item #9 / issue #23, explicitly deferred per the issue's
own framing, this proposal only needs correct sequential materialization
of `perception<A>`, `perception<B>`, `perception<C>`); any change to
`Flow`, `FlowNode`, `ArtifactDependencyGraph`, `TriggerPolicy`, or
`InputRole` themselves (Section 1.1 establishes these need none); any new
durable storage format beyond extending the existing `recordings.csv`/
`provenance.csv` schemas; a LangSmith-like visualization UI (already a
separate, previously diagnosed issue); and the `ArtifactRepository`
rename still deferred from Milestone 3 (unrelated to this issue, not
reopened by it).

---

## 5. Slice breakdown

Each slice below is written at the grain the Architect subagent expects
from a `SliceContract`: one coherent objective, not an implementation
prescription. Exact file lists and forbidden areas are the Architect's own
job to determine per slice, from the actual repository state at the time.
Slice codes use an `MI-` prefix (Multiple Instances) rather than a
guessed GitHub issue number, since the issue has not been filed yet.

1. **MI-A, Instance identity primitive.** Define what identifies one
   instance of a domain type (a hashable key, analogous in narrowness to
   how `ArtifactVersion` wraps a single integer). Purely additive, no
   wiring into `ArtifactRepository`, `Session`, or anything else yet.
   Resolves the Identity question.
2. **MI-B, Repository storage generalized.** Extend
   `ArtifactRepository`'s storage to `(type, instance key)`, with a
   stable default key preserving every current single-instance call site
   unchanged. Resolves Multiplicity for storage.
3. **MI-C, Provenance dependency alignment.** Extend
   `ArtifactProvenance.dependencies` to record which instance of each
   dependency a commit actually used. Depends on MI-A and MI-B. Resolves
   Alignment.
4. **MI-D, `Session.feed()` accepts multiple instances.** `feed()` commits
   one `ArtifactRecord` per given instance, each with `ArtifactOrigin.EXTERNAL`,
   using MI-B's storage and MI-A's identity. Depends on MI-B. Resolves
   part of Multiplicity and Lifecycle (instance introduction).
5. **MI-E, Per-instance firing and eligibility.** Generalize
   `Session._node_sessions`, `_last_known_values`, and
   `_fresh_since_last_firing` to the instance dimension, so
   `_is_eligible_to_fire` evaluates per instance and a propagation can
   contain several firings of the same node. Depends on MI-B, MI-D. This
   is the slice that answers what a Firing means under multiplicity, and
   is the largest slice in this plan; consider splitting it further once
   the Architect inspects the actual coupling between these three dicts.
6. **MI-F, NodeMemory scope decision and wiring.** Resolve R4 (per-instance
   vs. shared memory) as an explicit decision, recorded in
   `docs/refactor/`, then wire `NodeSession.memory` accordingly. Depends
   on MI-E.
7. **MI-G, Broadcasting.** A singleton artifact (no instance dimension of
   its own, such as `DeltaT`) participates correctly in every
   instance-level firing that consumes it. Depends on MI-E.
8. **MI-H, Collective dependencies (`Collection[T]`).** A node declared
   with `Collection[T]` resolves the currently known instances of `T` and
   is evaluated for eligibility under its own, collective readiness rule,
   distinct from per-instance `_is_eligible_to_fire`. Depends on MI-E,
   MI-G. Resolves Collective dependencies and, jointly with MI-I,
   Quiescence.
9. **MI-I, Lifecycle and fault isolation.** Instance removal/replacement
   within a session, and the decision from R9 (whether a sibling
   instance's firing failure aborts the propagation or is isolated).
   Depends on MI-E through MI-H.
10. **MI-J, Observability integration.** Extend `Session._artifact_id`,
    `NodeExecutionIdentity`, `ProvenanceEvent`, the durable CSV schemas,
    `replay.py`, and `graph.py` so per-instance firings and commits are
    correctly distinguishable in every existing observability surface.
    Depends on MI-E and MI-J's own predecessors being stable; deliberately
    last, since it only consumes identity the earlier slices establish
    and should not gate them.

A slice may turn out finer or coarser once an Architect invocation
actually inspects the code for it; this breakdown is a starting map, not a
binding contract. The Architect's own SliceContract for MI-A is where this
plan's authority actually takes effect.

---

## 6. Agents to instantiate, responsibilities, and pipeline

This repository already has a working, three-role autonomous pipeline
that has carried issues #1 through #22 to completion:
`.claude/agents/reed-architect.md`, `.claude/agents/reed-implementer.md`,
and `.claude/agents/reed-reviewer.md` (each with a `-escalated`, Sonnet-tier
variant for mechanical retries), orchestrated by
`.claude/skills/reed-refactor/SKILL.md`. This plan reuses that pipeline
exactly as written rather than defining new agents, since the existing
one is proven and this issue is architecturally the same kind of work
(a bounded slice sequence against accepted architecture) as every prior
issue it has handled.

**Architect** (`reed-architect`, tools `Read, Grep, Glob, Bash`, no write
access to `src/`, `tests/`, or `docs/`). Plans exactly one slice per
invocation: reads governing documentation and the specific files a slice
would touch, applies the ten Stop Conditions and the Slice Scope Rule, and
writes either a `slice_contract.yaml` or a `human_decision_request.yaml`.
For this issue, its governing documentation is this plan plus whatever
form the filed GitHub issue takes, in addition to the two documents it
already always reads (`docs/refactor/architectural_invariants.md`,
`docs/refactor/architectural_decision.md`).

**Implementer** (`reed-implementer`, tools `Read, Grep, Glob, Edit, Write,
Bash`). Implements exactly the given `SliceContract`, writes focused
tests, runs the full verification suite, and reports blast radius against
its own expectations. Bound by the Test Integrity Rule (never weaken an
assertion, never delete a failing target test to make it pass) and by
`guard_scope.py`, which mechanically blocks any edit outside the
SliceContract's declared areas.

**Reviewer** (`reed-reviewer`, tools `Read, Grep, Glob, Bash`, no write
access at all). Independently recomputes blast radius, re-reads every
changed file, re-runs the full suite and ruff itself rather than trusting
the Implementer's report, and checks specifically for test-integrity
violations and scope creep. Writes `PASS`, `FIX`, or
`HUMAN_DECISION_REQUIRED`.

**Pipeline**, per `SKILL.md`: for each slice, PLAN (Architect) then
IMPLEMENT (Implementer) then REVIEW (Reviewer); a `FIX` verdict returns to
IMPLEMENT with the Reviewer's `blocking_issues` only, up to a fix budget
of two attempts per slice before stopping for a human decision; a `PASS`
verdict proceeds to checkpoint and then to the next slice's PLAN,
automatically, without pausing for approval between slices. This
conversation, acting as the orchestrator, invokes each subagent via `Task`,
reads its YAML output directly (never a paraphrase), and never edits
`src/`, `tests/`, or `docs/` itself.

**One deliberate adaptation of `SKILL.md` Section 5 for this run.** The
orchestrator's own checkpoint step stages and commits each passed slice.
The standing rule for this conversation is that no git write command
(`add`, `commit`, `push`, or any other) runs here, by me or by any
subagent. This plan honors that rule by stopping at the checkpoint
boundary instead of performing it: after a slice reaches `PASS`, the
verified diff and the Reviewer's report are handed to Davi as they have
been throughout this conversation, for him to stage and commit at his own
pace, one slice at a time or in whatever grouping he chooses. The next
slice's PLAN, and specifically its `baseline.py capture`, only begins once
that commit exists, so the blast-radius comparison the design relies on
stays correct against a genuinely clean tree, exactly as Section 5 itself
already requires.

**Prerequisite before MI-A's first PLAN.** Once this plan is reviewed,
committing it under `docs/refactor/` (this file, as delivered) gives the
Architect a real file to read as this issue's scope statement, the same
way `docs/refactor_priority_order.md` served issue #4. Filing the GitHub
issue itself (title, description, and the review comment already drafted)
is independently useful as the durable, human-facing record, but the
Architect subagent reads repository files, not GitHub, so this document's
presence under `docs/refactor/` is what actually makes the pipeline runnable.

**Also before MI-A's first PLAN.** Correct `SKILL.md`'s bootstrap text (R6
above) so it names `docs/refactor/architectural_invariants.md` explicitly.
This is a small, independent documentation fix, unrelated to any
multi-instance slice, and should not be folded into MI-A's own scope.
