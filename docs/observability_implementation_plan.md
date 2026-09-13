# Reed Observability — Implementation Plan

Status: this document is the execution plan for building Issue #7 (observability) on top of
the harness already assembled. It does not introduce new architecture and does not repeat
what the other documents already say — it operationalizes them into a repeatable cycle and
an ordered path through the milestones. Read it alongside, not instead of:

- `docs/observability_agent_protocol.md` — operational rules for the implementing agent.
- `docs/observability_harness.md` — the milestone/slice table (`O1`-`O6`) and current slice.
- `docs/observability_refactor_guide.md` — the authority order and implementation policy.
- `docs/observability_implementation_state.md` — the live checkpoint this plan's cycle
  writes back into after every slice.

## 1. Why a separate plan document

The harness says *what* the slices are. The agent protocol says *how* an agent must behave
while implementing one. Neither one, on its own, spells out the repeatable loop that turns
"next row in the table" into a merged, verified, recorded change. This document is that
loop, plus the specific order the O1-O6 slices should actually be attempted in (which is not
always top-to-bottom inside a milestone — see Section 4).

## 2. The slice cycle

Every slice, without exception, goes through the same five stages. This is the operational
core of this plan; everything else in this document exists to feed the right slice into
stage 1.

```
 1. BREAK DOWN  ->  2. IMPLEMENT  ->  3. VALIDATE  ->  4. RECORD  ->  5. ADVANCE
```

### 2.1 Break down

Take the next slice from `observability_harness.md`'s current-slice pointer. Before writing
any production code, produce the Slice Plan required by
`observability_agent_protocol.md` §"Slice Plan Requirement" (name, milestone/row, design
section(s), current implementation inspected, regression tests, target tests, external
references, scope, non-scope, expected change surface, risks, definition of done,
implementation steps).

If, while filling in the plan, the slice turns out to bundle more than one coherent change
(e.g. "identity fields" quietly including "and also wire the durability boundary"), split it
into two slices before proceeding — per the Slice Scope Rule. A slice plan that cannot fit
its "Expected Change Surface" into a short, specific file list is a sign it is still too big.

Do not skip this stage even for a slice that looks trivial (e.g. O1b's UUID field). The
discipline is the point, not the paperwork — a skipped plan is where scope creep and
silent architectural decisions both enter.

### 2.2 Implement

Follow the plan. Touch only the files declared in the expected change surface unless a
genuine, explained deviation is required (per Blast-Radius Control). Follow
`observability_non_goals.md` as a checklist while writing code, not just while reviewing it
afterward — several of its items (scalar-only `value`, no `fsync` per call, no reserved
exception/cancellation record names) are the kind of thing that is easy to violate
incidentally while solving a narrower problem.

Stop immediately, per the Stop Conditions in `observability_agent_protocol.md`, if
implementation reveals that the slice would require resolving one of the two open items
(`flow_id`/`node_id` stability, `kind="event"`'s fate) as a side effect, or if the design
record and `observability_goals.md`/`observability_non_goals.md` disagree about what this
slice should do.

### 2.3 Validate

Two layers, both required:

1. **Targeted verification for the slice**: the specific test(s) named in the slice plan's
   "Target tests expected to move" actually move from failing/absent to passing: existing
   regression tests protecting current `Run`/`FlowNode`/`NodeContext`/`ArtifactRepository`
   behavior still pass unchanged.
2. **Baseline verification for the repo**: `uv run pytest -q -o addopts=''` and
   `uv run ruff check src tests` both run clean. Do not treat a slice as done on the
   strength of its own new tests alone if the wider suite has regressed.

If a check fails for a reason that cannot be explained, that is itself a Stop Condition —
do not iterate blindly on the code until the test happens to pass.

### 2.4 Record

Update `docs/observability_implementation_state.md`:

- Append a completed-slice entry (design section(s) implemented, files changed, tests run,
  deviations, new open questions, follow-up work).
- If the slice resolved one of the two flagged open items, that resolution must first be
  written back into `docs/observability_design.md` as a new round/section (per the harness
  table's O1a/O2e rows), and only then marked resolved in the state file's open-questions
  log — never the reverse order.
- If a new open question surfaced during implementation, log it here immediately, even if
  it does not block the current slice.

Then update `docs/observability_harness.md`'s "Current slice" section to point at the next
slice (Section 4 below gives the default ordering), and its "Milestones and slices" table
stays as the durable plan of record — the state file is the log of what actually happened
against that plan.

### 2.5 Advance

**Continuous execution is authorized (2026-09-13, superseding the former One-Slice
Termination Rule — see `observability_agent_protocol.md`'s "Continuous Execution
Policy").** Completing a slice's record step now means immediately beginning the next
slice's "break down" stage (2.1), not stopping to wait for a new instruction. The five-stage
cycle itself is unchanged; only what happens after stage 4 changes: chain directly into the
next slice's stage 1, for every slice in the currently authorized sequence, stopping only
for the genuine blockers in `observability_agent_protocol.md`'s Stop Conditions (an
unresolvable architectural contradiction, an unauthorized destructive/irreversible action,
an unrecoverable repository state, or reaching the end of the authorized sequence).

## 3. Reporting

After stage 4 of every slice, report to whoever requested the work: what changed, which
design-record section(s) were implemented, which files changed, which tests ran and passed,
whether the state file and harness were updated, and any ambiguity or follow-up work — this
mirrors `observability_agent_protocol.md`'s "Reporting Requirement" and should not be
treated as optional even when the change is small.

## 4. Recommended slice order

`observability_harness.md` already encodes the dependency structure between milestones
(O1 blocks O2-O6; O2 blocks O3; O1+artifact-commit path blocks O4; O1 blocks O5's minimal
form; O2-O4 block O6). This section makes the *intra-milestone* ordering explicit, since the
harness table lists slices top-to-bottom without always stating which ones are strictly
sequential versus merely grouped.

1. **O1a** — resolve `flow_id`/`node_id` stability (blocks all of O1b-O1f and transitively
   everything else). Must produce a new round/section in `observability_design.md` before
   O1b starts.
2. **O1b -> O1c -> O1d -> O1e -> O1f**, in that order: `execution_id`/`flow_id` on `Run`
   depends on nothing else in O1; `node_id` on `FlowNode` (O1c) is independent of O1b but
   listed after it for review clarity; `node_execution_id` (O1d) depends on `node_id`
   existing; `execution_seq` (O1e) depends on `node_execution_id` minting existing;
   `NodeContext`'s identity bundle (O1f) depends on all four fields existing to expose.
3. **O2a -> O2b -> O2c -> O2d**, then **O2e** last: the `Instrument` dataclass (O2a) has no
   dependency beyond O1; `flow.add(instruments=...)` (O2b) depends on O2a; declared-mode
   `ctx.record()` (O2c) depends on O2b; lazy-mode `ctx.record()` (O2d) is independent of O2b/
   O2c and could in principle be built first, but is sequenced after so the declared path
   (the primary, recommended API per `observability_goals.md` §2.2) lands first and lazy
   mode is visibly the fallback, not the baseline. O2e (`kind="event"`'s fate) is deliberately
   last in the milestone: resolving it earlier risks shaping O2a-O2d around an unresolved
   decision.
4. **O3a -> O3b -> O3d -> O3c -> O3e**: the store interfaces (O3a) and CSV writer (O3b) come
   first; `manifest.json` (O3d) is a thin layer on top of O3b and is sequenced before the
   durability-boundary flush wiring (O3c) so O3c has a concrete writer+manifest to flush
   into; `instruments.json` (O3e) is independent of O3b-O3d (it derives from Flow composition,
   not from recordings) and is placed last only because it is lower-risk and can slot in
   without blocking the recording path.
5. **O4a -> O4b -> O4c**: schema first, then the two emission sites, `generated` before
   `used` since a `used` event without any `generated` event to reference is meaningless for
   testing.
6. **O5a -> O5b -> O5c**: the ring buffer (O5a) has no dependency beyond O1; the terminal
   renderer (O5b) depends on O5a; post-hoc replay (O5c) depends on O3/O4 existing and is
   explicitly optional/lower priority.
7. **O6a, O6b, O6c, O6d**: no strict order between these four; take them in whatever order
   matches actual demand once O2-O4 exist. None are required for Issue #7's core scope.

This ordering is a default, not a constraint the agent protocol enforces — if a future
session has a concrete reason to reorder (e.g. O5a is wanted early for visibility during O2/
O3 development), that is a judgment call to make explicitly and record in
`observability_implementation_state.md`, not a violation of this plan.

## 5. Relationship to the two open items

O1a and O2e are not ordinary slices — each one's "definition of done" includes writing a
resolution back into `observability_design.md` as a new round, because both
`observability_goals.md` and `observability_non_goals.md` currently describe the *absence*
of a decision here as the correct state. Until O1a lands, no later slice may assume "some
UUID will do" for `flow_id`/`node_id` (`observability_non_goals.md` §10 says this
explicitly); until O2e lands, no later slice may quietly reintroduce `kind="event"` or
quietly drop non-metric facts. Treat both as design work first, implementation second, even
though they are scheduled as harness slices.

## 6. Definition of done for the observability build

The build reaches a reportable milestone-complete state when, for a given milestone, every
slice's own definition of done is met, the full baseline (`pytest` + `ruff`) is clean, and
`observability_implementation_state.md`'s completed-slices log accounts for every slice in
that milestone's table. The build reaches Issue #7's overall definition of done when O1-O5
are complete (O6 is explicitly lower-priority tooling, not required for the issue's core
scope per `observability_non_goals.md` §1) and the pre-Issue-4 terminal trace experience
(O5b) is demonstrably restored on the new identity/storage foundation.
