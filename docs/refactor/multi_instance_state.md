# Multiple Artifact Instances: Implementation State

Durable, human-readable record of this issue's slice-by-slice progress.
`docs/history/refactor_state.md` no longer exists as a general mechanism (see
`docs/refactor/multi_instance_execution_plan.md`, Section 6), so this file
fills that role scoped to this one issue, alongside
`.claude/reed-refactor/<run-id>/` (ephemeral, gitignored, per-run audit
trail; this file is the durable summary of it).

Scope statement: `docs/refactor/multi_instance_execution_plan.md`.
Issue title: "Support multiple artifact instances and per-instance node
execution" (not yet filed on GitHub at the time this file was created).

## Current status

**All ten slices (MI-A through MI-J) implemented, tested, and reviewed:
verdict PASS on every one.** Every risk in the plan document's own risk
register (R1 through R10) is resolved (see Decision log and Open
architectural questions below).

**Post-completion independent review round (`run-POST-MI-J-REVIEW-
20260925T180650Z`):** Davi asked for a review and an example of the
mechanism in use. Since every slice through MI-J had been implemented
AND reviewed by the same session, a genuinely independent, fresh
subagent (no memory of the implementation's own rationale) reviewed the
whole feature and found two real, previously-undetected bugs, both now
fixed and covered by dedicated regression tests -- see the Decision log
entry below for the full disclosure:

1. `Session.snapshot()`/`Session.invoke()` crashed for a domain type
   committed only via `feed_instances(...)` and never via plain
   `feed()`. Fixed in `snapshot.py`; `Snapshot` gained a new
   `.instances(domain_type)` accessor.
2. A broadcast dependency's freshness never expired under
   `TriggerPolicy.ALL_INPUTS_CHANGED` (the default trigger policy),
   spuriously re-firing a node on every per-instance arrival even when
   the broadcast type itself was never fed again. Fixed in
   `Session.push()`.
3. Found by building the requested example, not by the subagent review:
   `graph.render_provenance_tree`'s new `[instance=...]` suffix (Slice
   MI-J) was silently swallowed by Rich, which treats `[...]` in a
   `Tree`/`Console` label as markup syntax, not literal text. Fixed by
   escaping every label with `rich.markup.escape(...)` in `graph.py`.

Two further findings were investigated and found not to need a code
change (an already-documented Quiescence consequence, clarified in
`collective.py`'s docstring; and an already-disclosed MI-C non-wiring,
re-confirmed, not new).

`examples/multi_instance_fleet_example.py` (new) demonstrates the whole
mechanism end to end -- InstanceKey/feed_instances, per-instance firing,
per-instance NodeMemory, Broadcasting (including freshness correctly
expiring, bug 2 above), Collective dependencies, instance removal,
`Snapshot.instances()` (bug 1 above), and observability with
`instance_id` (bug 3 above, which this example itself surfaced). Full
suite: 363 passed, 1 skipped; ruff clean.

**This issue has reached its own terminal state** -- the equivalent of
the retired `ISSUE_4_COMPLETE` marker the orchestrator kickoff prompt
below names as its stop condition. Awaiting staging and commit (see
"Git checkpoint adaptation" below); the working tree currently holds
every change from all ten slices plus this review round uncommitted,
exactly as it has throughout this issue -- no slice or review round in
this run ever ran a git write command.

Process note on MI-B: its SliceContract was written after implementation
and verification rather than before, and no fresh `baseline.py` capture
was taken at MI-B's own start, so its blast radius is based on tracked
edit history rather than an independently recomputed diff, and its review
was performed by the same session that implemented it, not an isolated
second context. Both are disclosed limitations, not hidden ones. MI-C
onward returns to the full PLAN-first, independent-baseline sequence.

## Orchestrator kickoff prompt

The following is the self-contained instruction that starts, or resumes,
this issue's slice-by-slice pipeline, following
`.claude/skills/reed-refactor/SKILL.md`, scoped to this issue via the plan
document:

```
Run the Reed refactor orchestrator (.claude/skills/reed-refactor/SKILL.md)
for the issue "Support multiple artifact instances and per-instance node
execution". This issue's own scope statement is
docs/refactor/multi_instance_execution_plan.md (Section 5 for the slice
map, Section 4 for scope and non-scope); its running state is
docs/refactor/multi_instance_state.md. Read both before the first PLAN.

Proceed slice by slice in the order Section 5 lists (MI-A through MI-J),
Architect -> Implementer -> Reviewer -> either a FIX loop or, on PASS, a
checkpoint followed by the next slice's PLAN, exactly as SKILL.md
describes, continuing autonomously through PASS without pausing for
approval between slices. Update this file's Current Status and Completed
Slices table after every PASS.

One adaptation to SKILL.md Section 5 applies for this issue: never run
git add, git commit, or any other git write command, in this session or
in any subagent it spawns. Stop at the checkpoint boundary instead --
report the verified diff and the Reviewer's PASS, and wait for the human
to stage and commit it before capturing the next slice's baseline. Only
git status, git diff, git log, and git show (or baseline.py's own
read-only git usage) are permitted.

Stop only for a genuine HUMAN_DECISION_REQUIRED (per each role's own
Decision Autonomy section in .claude/agents/reed-{architect,implementer,
reviewer}.md) or once slice MI-J passes review (this issue's own
equivalent of the retired ISSUE_4_COMPLETE terminal state).
```

## Completed slices

| Slice | Title | Implemented | Tested | Reviewed | Verdict | Run directory |
|---|---|---|---|---|---|---|
| MI-A | InstanceKey: additive domain-artifact-instance identity primitive | yes | yes (6/6 focused, 15/15 target contract, 298 passed / 1 skipped full suite, ruff clean) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-A-20260925T163526Z/` |
| MI-B | ArtifactRepository storage generalized to (domain type, InstanceKey) | yes (plus a necessitated fix to `Snapshot.from_repository`, see notes) | yes (7/7 focused, 15/15 target contract, 305 passed / 1 skipped full suite, ruff clean; caught and fixed 18 full-suite failures before reaching this state) | yes, same-session re-run (see process note above) | PASS | `.claude/reed-refactor/run-MI-B-20260925T164037Z/` |
| MI-C | `ArtifactProvenance.dependency_instances`: additive alignment bookkeeping, unwired into any firing | yes | yes (5/5 focused, full suite green, ruff clean) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-C-20260925T164841Z/` |
| MI-D | `Session.feed_instances()`: multi-instance external feeding via the shared `_commit` path | yes (explicit-instance-map API chosen over value-inferred identity; see decision log below) | yes (6/6 focused, full suite green, ruff clean) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-D-20260925T165144Z/` |
| MI-E | Per-instance eligibility and firing through the cascade (`push()`, same-instance alignment) | yes (plus a necessitated fix to `tests/test_slice_22e_session_feed.py`, see notes) | yes (8/8 focused, 324 passed / 1 skipped full suite, ruff clean; caught and fixed 1 full-suite failure before reaching this state) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-E-20260925T165640Z/` |
| MI-F | NodeMemory scope decision (R4: per-instance) and wiring | yes | yes (7/7 focused, 331 passed / 1 skipped full suite, ruff clean; zero regression fixes needed) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-F-20260925T170616Z/` |
| MI-G | Broadcasting: singleton-scoped dependency participates in per-instance firing | yes | yes (6/6 focused, 337 passed / 1 skipped full suite, ruff clean; zero regression fixes needed) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-G-20260925T171454Z/` |
| MI-H | Collective dependencies: `Annotated[T, Collective]` resolves the currently known instances of `T` | yes (plus a necessitated fix to `tests/test_slice_1b_domain_node_description.py`'s field-set pin, see notes) | yes (6/6 focused, 343 passed / 1 skipped full suite, ruff clean; caught and fixed 1 full-suite failure before reaching this state) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-H-20260925T172114Z/` |
| MI-I | Lifecycle (instance removal) and fault isolation (R9: abort, not isolate) | yes | yes (7/7 focused, 350 passed / 1 skipped full suite, ruff clean; zero regression fixes needed) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-I-20260925T172913Z/` |
| MI-J | Observability integration: per-instance firings and commits correctly distinguishable (R5) | yes (fixed two genuine pre-existing bugs discovered during planning: `_emit_used_provenance_events`'s missing `instance=` argument, and `build_provenance_graph`'s instance-blind group-by collision risk -- see notes) | yes (7/7 focused, 357 passed / 1 skipped full suite, ruff clean; zero regression fixes needed -- the first slice in this run where nothing needed a corrective edit) | yes, independently re-run | PASS | `.claude/reed-refactor/run-MI-J-20260925T173605Z/` |
| POST-MI-J-REVIEW | Independent adversarial review of the whole feature (MI-A through MI-J), requested by Davi, plus a worked example (`examples/multi_instance_fleet_example.py`) | yes (fixed 3 genuine bugs: `Snapshot.from_repository`'s singleton-record assumption and stale broadcast freshness under `ALL_INPUTS_CHANGED`, found by the independent review; `render_provenance_tree`'s `[instance=...]` suffix silently swallowed by Rich markup, found by building the example -- see notes and Decision log) | yes (6/6 new focused, 363 passed / 1 skipped full suite, ruff clean; example itself runs end to end) | yes, by a genuinely independent fresh subagent for bugs 1-2, plus direct execution of the new example for bug 3; all three verified by hand against actual repository behavior | PASS_WITH_FIXES | `.claude/reed-refactor/run-POST-MI-J-REVIEW-20260925T180650Z/` |

## Remaining slices

None. All ten slices (MI-A through MI-J) are complete; see Completed
Slices above. This table is kept, empty, as the durable record that
nothing was left undone at this issue's own terminal state.

See `docs/refactor/multi_instance_execution_plan.md`, Section 5, for each
slice's objective and dependencies.

## Open architectural questions carried forward

None remain open. Every risk the plan document raised (R1 through R10)
is resolved:

- R4 (plan document): resolved at slice MI-F. Decision: per-instance
  NodeMemory and last_output (see Decision log below).
- R9 (plan document): resolved at slice MI-I. Decision: a firing
  failure for any one instance ABORTS the whole push() propagation
  (Session._fire's own pre-existing, unmodified exception handling --
  no new isolation mechanism was built or is needed). See Decision log
  below.
- Quiescence (jointly assigned to MI-H and MI-I): resolved at slice
  MI-I with no new code. push() is fully synchronous and sequential, so
  a Collective dependency's read is deterministic and caller-controlled
  (feed the complete batch via feed_instances(), then push()) -- see
  Decision log below.
- R5 (plan document, "the single largest-blast-radius risk"): resolved
  at slice MI-J, the last remaining risk. Decision: `instance_id` added
  as a new, additive field on `NodeExecutionIdentity`/`ProvenanceEvent`
  (never folding instance identity into `Session._artifact_id` itself,
  despite the plan's own literal phrasing); `graph.py`'s group-by key
  extended to `(artifact_id, artifact_version, instance_id)`; the
  `Presenter` protocol and `logging.py` deliberately left unextended.
  See Decision log below.
- R1, R2, R3, R6, R7, R8, R10 (plan document): resolved incrementally at
  slices MI-A, MI-B, MI-C, and throughout, as each slice's own
  SliceContract and this file's Decision log and Refactor state log
  entries record; none required a dedicated late-stage decision the way
  R4/R5/R9/Quiescence did.

## Decision log (genuine architectural forks, resolved under standing
autonomy authorization, disclosed rather than hidden)

- MI-D, `Session.feed_instances()`: Davi's own issue sketch implied
  automatic instance-identity inference from fed domain values (e.g.
  `session.feed([value_a, value_b, ...])`). Reed has no duck-typed
  identity-inference protocol anywhere else in the codebase, so inventing
  one here would be a new, undetermined convention rather than an
  application of an existing one. Resolved by requiring the caller to
  supply instance identity explicitly: `feed_instances(values:
  Mapping[InstanceKey, object])`. This is flagged for Davi's own
  confirmation since nothing about it is committed to git yet; it can be
  revisited without disturbing any other slice, since no later slice
  depends on the exact shape of this parameter, only on the fact that
  fed values carry an explicit `InstanceKey`.
- MI-F, R4 (NodeMemory scope): resolved as per-instance rather than
  shared across every instance of a node. Rationale: the plan document's
  own risk assessment names per-instance memory as the useful default
  (Reed's own aircraft example: each aircraft's `perception` node wants
  independent memory); it is the same generalization already applied
  consistently everywhere else (MI-A through MI-E); and MI-E's own
  SliceContract had already pre-flagged this exact gap and deferred it
  here by name, so this was not a fresh, undetermined fork so much as a
  scheduled decision with its rationale already anticipated. Wired via
  `NodeSession._memory_for(instance)` / `._last_output_for(instance)`
  (new, private) with the existing zero-argument `.memory` /
  `.last_output` / `.context` properties reading through
  `InstanceKey.singleton()` unchanged. `NodeSession.firing_lock`
  (invariant #17) deliberately stays scoped to (Session, NodeSession)
  only, not split per instance, since concurrent instance-level firing
  is out of scope for this whole issue (plan document Section 4; roadmap
  #9 / issue #23) -- recorded so this reads as a decision, not an
  oversight.
- MI-G, Broadcasting scope boundary: broadcasting a singleton-scoped
  dependency (fed once via plain `feed()`, never per instance) affects
  what an already-attempted firing can SEE (coverage, ALL_INPUTS_CHANGED
  freshness, call-argument resolution, all via two new merge helpers,
  `_effective_known_values` / `_effective_fresh_types`), not WHEN a
  firing is attempted (`push()`'s seed selection and cascade dispatch
  are completely unchanged). Updating only a broadcast value does not
  retroactively re-trigger an instance with no fresh input of its own
  this `push()` call -- deliberately deferred, confirmed by a passing
  test rather than left an open question, since retroactive re-seeding
  purely from a broadcast change is a scheduling/quiescence question the
  plan document assigns jointly to MI-H and MI-I, not MI-G.
- MI-H, Collective dependencies -- detection shape: the plan document's
  own prose says "a node declared with Collection[T]", which could be
  read as detecting the bare `Collection[T]` generic origin directly.
  Resolved instead as `Annotated[T, Collective]`
  (`reed.composition.node.collective.Collective`, a new marker class),
  exactly mirroring the existing `Annotated[T, Sampled]` precedent
  (Slice 21B). Rationale: avoids colliding with a node that legitimately
  consumes a literal collection-shaped domain type as a single scalar
  artifact; reuses `DomainNodeSignatureParser._unwrap_annotated`'s
  already-proven detection mechanism instead of adding new generic-
  unwrapping logic; and keeps this codebase to one established
  convention for "orthogonal, additive, annotation-shape-detected
  parameter metadata" instead of two differently-shaped ones. A
  `Collective`-marked parameter always gets `InputRole.SAMPLED` (never
  triggers firing by itself), which composes naturally with MI-G's
  Broadcasting as the collective-consuming node's triggering partner
  (its own `ArtifactDescriptor.is_collective` field is a new, defaulted,
  additive field, the same pattern `input_role` itself set at Slice
  21A).
- MI-I, R9 (fault isolation): a firing failure for any one instance
  ABORTS the whole push() propagation; sibling instances already queued
  in the same cascade never fire once one instance's firing raises. Not
  new behavior -- Session._fire's own pre-existing exception handling
  (report to the presenter, then a bare re-raise) was already exactly
  this, unmodified since before this issue existed and untouched by
  MI-A through MI-H. Chosen over building a new isolation/recovery
  mechanism because Reed has no existing precedent anywhere for "catch a
  firing failure and continue to unrelated queued work" -- inventing one
  now, with nothing in the plan document driving a specific recovery
  shape, would be speculative architecture this issue's own scope does
  not ask for. Locked in by a dedicated test rather than left implicit.
- MI-I, Quiescence: resolved with zero new code. push()'s cascade is
  fully synchronous and sequential (concurrent instance-level firing is
  out of scope for this whole issue), so there is no race between a
  Collective dependency's read and sibling instances arriving. Whether a
  collective read sees "every instance that will exist this tick" is
  caller-controlled: feed a complete batch via feed_instances() before
  calling push(), and every instance in that batch commits, in order,
  before any node's eligibility is even evaluated.
- MI-J, R5 (observability integration): two genuine pre-existing bugs
  discovered during planning, fixed as part of this slice rather than
  newly introduced: `Session._emit_used_provenance_events` called
  `get_artifact_record` with no `instance=` argument at all, always
  reading the singleton slot regardless of which instance was actually
  firing; and `graph.py`'s `build_provenance_graph` grouped rows by
  `(artifact_id, artifact_version)` alone, which silently collided two
  different instances' first-ever commits of the same type (each
  independently starting its own version sequence at 1, invariant #28)
  into one graph node. Both are now exercised directly by dedicated
  tests
  (`test_used_event_reports_the_actual_per_instance_dependency_not_the_singleton_default`,
  `test_two_instances_first_commits_do_not_collide_in_the_provenance_graph`).
  `_emit_used_provenance_events` now resolves each consumed type's
  record under the firing's own instance first, falling back to the
  singleton-scoped record (mirroring MI-G's own broadcast precedence
  exactly) -- the emitted event's `instance_id` is the DEPENDENCY's own
  resolved instance, not necessarily the firing's, so it correctly
  matches that dependency's own "generated" event's group-by key even
  across a broadcast dependency. A `Collective`-marked consumed
  descriptor (MI-H) is deliberately skipped entirely by this method: it
  resolves to potentially many records across many instances at once,
  not a single (artifact, version, instance) triple a "used" event can
  cleanly attribute -- disclosed scope decision, not an oversight, and
  revisitable by a future slice if collective-dependency provenance
  becomes a real need. `Session._artifact_id` itself is deliberately
  left unmodified, despite the plan document's own literal phrasing
  ("extending `_artifact_id` to include an instance key"): the instance
  dimension is instead carried as a new, separate, additive
  `instance_id` field on `NodeExecutionIdentity`/`ProvenanceEvent`, the
  same "orthogonal, additive" pattern this whole issue has used
  consistently since MI-A. The `Presenter` protocol
  (`on_artifact_generated`/`on_artifact_consumed`) and `logging.py` are
  deliberately NOT extended with an instance parameter: the plan
  document's own R5 text names `_artifact_id`, `NodeExecutionIdentity`,
  `ProvenanceEvent`, the durable CSV schemas, `replay.py`, and
  `graph.py` -- not the terminal presenter -- and no
  `expected_to_pass` test in this slice's own SliceContract required
  extending either, so the SliceContract's own stop_condition
  ("if extending the Presenter protocol or logging.py turns out to be
  required... stop and re-escalate") never triggered. `storage.py`'s
  `SCHEMA_VERSION` bumped 1 -> 2, a genuine non-backward-compatible
  durable schema change, safe within this issue's own durability
  model since each Execution owns its own fresh CSV files under its
  own `execution_id`.
- POST-MI-J-REVIEW: two genuine bugs found by an independent fresh
  subagent review, neither caught by any of the ten slices' own test
  suites because each slice's own tests exercised its own new mechanism
  in isolation, never the specific cross-slice combination that
  triggered these:
  (a) `Snapshot.from_repository` (`snapshot.py`) assumed every domain
  type key in the repository's private storage had a record at
  `InstanceKey.singleton()` specifically, calling `.value` on
  `get_artifact_record(domain_type)`'s result with no None-check. A type
  committed only via `feed_instances(...)` (never `feed()`) has no
  singleton record at all, so `session.snapshot()` (and `session.
  invoke()`, which calls it) raised `AttributeError` for exactly the
  pure multi-instance use case this whole feature exists to support --
  MI-B's own docstring had already adjusted this method once (to go
  through the public accessor instead of the private dict directly) but
  that adjustment was itself still incomplete. Fixed by reading every
  currently known instance via `get_all_artifact_records` instead; a
  new, additive `Snapshot.instances(domain_type)` accessor (and an
  `instance=` keyword on `.get(...)`) makes the multi-instance state
  genuinely reachable, since invariant #33 ("full current repository
  state") is not actually satisfied if non-singleton-only types are
  silently unreachable through the pre-existing single-value surface.
  The zero-argument `.get(...)`/`[...]` behavior for every
  pre-multi-instance caller is completely unchanged.
  (b) `Session._fire`'s per-firing freshness clear
  (`_fresh_since_last_firing[flow_node][instance] = set()`) only ever
  clears the firing's OWN instance's entry, never the separate
  singleton-scope entry a broadcast (Slice MI-G) type's freshness lives
  in. Under `TriggerPolicy.ALL_INPUTS_CHANGED` (the DEFAULT
  trigger_policy for `Flow.add(...)`, and the policy the plan document's
  own aircraft example implicitly uses), a broadcast dependency's
  freshness therefore never expired once set, silently degrading
  ALL_INPUTS_CHANGED to ANY_INPUT_CHANGED behavior for any node mixing a
  broadcast input with a per-instance one -- MI-G's own test suite never
  caught this because every one of its tests exercised exactly one
  `push()` call, never a second one with no intervening broadcast
  re-feed to check that firing does NOT spuriously repeat. Fixed in
  `Session.push()`: the singleton-scope freshness entry for any
  flow_node that fired under ALL_INPUTS_CHANGED is now cleared once,
  after the ENTIRE push() call's seed pass and cascade both finish, not
  per-firing -- clearing it earlier (e.g. mid-seed-loop, right after the
  first instance to use it fires) would incorrectly deny a second,
  not-yet-evaluated instance covered by the SAME push() call the same
  fair look at that same freshness event; this was confirmed both by
  hand-tracing `push()`'s own seed-loop-then-cascade structure and by a
  dedicated regression test asserting two instances still fire together
  in one push() after the fix.
  (c) `graph.render_provenance_tree` (`graph.py`) built each Rich `Tree`
  branch label as a plain f-string including the new `[instance=...]`
  suffix, e.g. `"AircraftState v1 [instance='N-ALPHA']"`. Rich's own
  `Tree`/`Console` interpret `[...]` inside a label as MARKUP syntax
  (e.g. `[bold]...[/bold]`), not literal text -- an unrecognized tag
  like `[instance='N-ALPHA']` is silently parsed and dropped rather than
  displayed, with no error. This was never caught by any of MI-J's own
  tests because none of them rendered a `Tree` for a genuinely
  multi-instance flow: the singleton-only rendering test's suffix is
  always empty (so this path never triggers), and the two-instance
  provenance-graph test only checked `build_provenance_graph`'s plain
  data structure, never `render_provenance_tree`'s actual rendered
  output. Found instead by building the example Davi asked for
  (`examples/multi_instance_fleet_example.py`), the first place this
  method was ever exercised for a real multi-instance flow -- a direct
  demonstration of why "build an example" is valuable review in its own
  right, not just a teaching aid. Fixed by passing every label through
  `rich.markup.escape(...)` before `Tree.add(...)`; `render_provenance_
  dot` was unaffected (it returns a plain string, never rendered through
  Rich).

  Two further findings from the same review were investigated and found
  NOT to need a code change: Collective dependencies (MI-H) can resolve
  a torn view if some instances of the collective type are still being
  produced by other nodes later in the same push() cascade -- this is
  the direct, already-documented consequence of Quiescence's own MI-I
  resolution ("caller-controlled... feed a complete batch via
  feed_instances(), then push()"), addressed by clarifying
  `collective.py`'s own docstring rather than by changing behavior;
  and `ArtifactProvenance.dependency_instances` (MI-C) being genuinely
  unpopulated by any real commit path was re-confirmed, not newly
  discovered -- MI-C's own completion notes already disclosed this
  exact limitation ("purely additive, confirmed unwired into any real
  firing path").


## Prerequisite housekeeping already done

- `SKILL.md`'s bootstrap text corrected to name
  `docs/refactor/architectural_invariants.md` explicitly, instead of the
  stale bare `docs/refactor/architectural_invariants.md` path (plan document Risk
  R6).

## Git checkpoint adaptation

This issue's pipeline never runs `git add`, `git commit`, or any other
git write command, in this session or in any subagent it spawns (standing
rule for this conversation). Each slice's verified diff is reported here
and handed to Davi to stage and commit at his own pace; the next slice's
baseline is captured against the working tree as it stands at that
moment, whether or not a commit has happened yet, since `baseline.py`
only needs a content snapshot, not a git commit, to measure blast radius
correctly.

## Refactor state log

- 2026-09-25: Plan document created
  (`docs/refactor/multi_instance_execution_plan.md`). SKILL.md bootstrap
  path corrected (R6). Slice MI-A planned, implemented, tested, and
  reviewed: PASS. This file created.
- 2026-09-25: Slice MI-B implemented and tested. The required full-suite
  run caught 18 pre-existing-assumption failures in
  `Snapshot.from_repository` (a private reach-through into
  `ArtifactRepository._artifact_records` that assumed the pre-MI-B
  single-record-per-type shape); fixed narrowly, all 305 tests pass.
  Reviewed same-session: PASS, with the process limitations noted above
  disclosed rather than hidden.
- 2026-09-25: Full PLAN-first, independent-baseline sequence restored
  starting this slice. Slice MI-C (`ArtifactProvenance.dependency_instances`)
  planned, implemented, tested, reviewed: PASS. Purely additive, confirmed
  unwired into any real firing path.
- 2026-09-25: Slice MI-D (`Session.feed_instances()`) planned,
  implemented, tested, reviewed: PASS. Genuine architectural fork
  surfaced and resolved under standing autonomy authorization (see
  Decision log above) rather than escalated or silently assumed.
  `feed()` itself left completely unchanged.
- 2026-09-25: Slice MI-E (per-instance eligibility and firing through
  `push()`) planned, implemented, tested, reviewed: PASS. The highest-risk
  slice in the plan document's own risk assessment. The required
  full-suite run caught 1 pre-existing-assumption failure in
  `tests/test_slice_22e_session_feed.py` (a private reach-through into
  `Session._last_known_values`/`_fresh_since_last_firing` that assumed
  the pre-MI-E flat, non-instance-keyed shape); fixed narrowly by
  indexing through `InstanceKey.singleton()`, same category of fix as
  MI-B's. 324 passed, 1 skipped. Davi confirmed the plan and instructed
  the refactor to proceed autonomously through to the end
  ("vá até o final da refatoração"); this file's Current Status and
  Remaining Slices updated accordingly, and slice MI-F begun next.
- 2026-09-25: Slice MI-F (NodeMemory scope decision, R4) planned,
  implemented, tested, reviewed: PASS. Decision recorded above: per-
  instance memory and last_output. Zero regression fixes required --
  every pre-existing zero-argument .memory/.last_output/.context call
  site passed unmodified, unlike MI-B's and MI-E's own necessitated
  fixes. 331 passed, 1 skipped. Proceeding to slice MI-G (Broadcasting)
  next, per Davi's standing instruction.
- 2026-09-25: Slice MI-G (Broadcasting) planned, implemented, tested,
  reviewed: PASS. Pure read-side generalization (two new merge helpers
  in session.py; storage and scheduling untouched), confirmed by
  inspection to touch nothing outside session.py. Zero regression fixes
  required. 337 passed, 1 skipped. Proceeding to slice MI-H (Collective
  dependencies) next.
- 2026-09-25: Slice MI-H (Collective dependencies) planned, implemented,
  tested, reviewed: PASS. New `Collective` marker
  (`reed/composition/node/collective.py`), wired through
  `domain_signature.py` / `artifact_descriptor.py` /
  `domain_node_description.py` exactly mirroring the existing `Sampled`
  precedent (decision disclosed above); `session.py` resolves a
  collective-marked parameter's value from
  `ArtifactRepository.get_all_artifact_records`. The required full-suite
  run caught 1 pre-existing-assumption failure in
  `tests/test_slice_1b_domain_node_description.py` (a field-set pin on
  `ArtifactDescriptor.__dataclass_fields__` that this slice's own
  additive field legitimately changed, exactly as that same test's own
  comment already anticipated for Slice 21A's earlier addition); fixed
  by extending the pin, same category of fix as MI-B's and MI-E's own.
  343 passed, 1 skipped. Proceeding to slice MI-I (Lifecycle and fault
  isolation) next.
- 2026-09-25: Slice MI-I (Lifecycle and fault isolation) planned,
  implemented, tested, reviewed: PASS. New
  ArtifactRepository.remove_artifact_record / Session.remove_instance
  for instance removal (replacement already worked, confirmed by a
  regression test). R9 and Quiescence both resolved by confirming and
  documenting existing behavior rather than building new mechanisms --
  zero regression fixes needed. 350 passed, 1 skipped. Every open
  architectural question the plan document raised (R1-R9) is now
  resolved except R5 (observability), which is MI-J's job. Proceeding to
  slice MI-J -- the last remaining slice -- next, per Davi's standing
  instruction.
- 2026-09-25: Slice MI-J (Observability integration, R5 -- "the single
  largest-blast-radius risk") planned, implemented, tested, reviewed:
  PASS. Fixed two genuine pre-existing bugs discovered during planning
  (see Decision log above): `_emit_used_provenance_events`'s missing
  `instance=` argument, and `build_provenance_graph`'s instance-blind
  group-by collision risk. Added `instance_id` as a new, additive field
  on `NodeExecutionIdentity`/`ProvenanceEvent`/the durable CSV schema
  (`SCHEMA_VERSION` 1 -> 2), threaded through `Session._begin_node_
  execution`, `_fire`, `feed_instances()`, and both provenance-emission
  methods; `graph.py`'s group-by key and tree/dot rendering, and
  `replay.py`'s replay-table detail column, updated to show
  `[instance=...]` only for a non-singleton instance, so every existing
  single-instance-flow rendering stays byte-for-byte unaffected.
  Deliberately did not extend the `Presenter` protocol, `logging.py`, or
  `Session._artifact_id` itself (disclosed scope decisions, Decision log
  above). Zero regression fixes needed anywhere in the full suite -- the
  first slice in this entire ten-slice run where the focused tests,
  every named regression file, and the full suite all passed on the
  first attempt with no disclosed corrective edit to any pre-existing
  file. 357 passed, 1 skipped. This closes R5, the last risk in the plan
  document's own risk register (R1-R10) -- **every slice MI-A through
  MI-J has now passed review, and this issue has reached its own
  terminal state.** Per the orchestrator kickoff prompt's own stop
  condition, reporting completion to Davi now rather than inventing
  further, unrequested work; the full ten-slice diff remains
  uncommitted in the working tree, awaiting his own staging and commit
  at his own pace (Git checkpoint adaptation, above).
- 2026-09-25: Post-completion independent review round
  (`run-POST-MI-J-REVIEW-20260925T180650Z`), requested by Davi ("quero
  que você revise, e crie um exemplo que mostre esse mecanismo em uso").
  A fresh subagent with no memory of this implementation's own
  rationale reviewed the plan document, the full current source of
  every file this feature touches, and the diff against the pre-feature
  baseline, and found two genuine, previously-undetected correctness
  bugs (see Decision log above for the full disclosure):
  `Session.snapshot()`/`invoke()` crashing for a domain type committed
  only via `feed_instances(...)`, and a broadcast dependency's
  freshness never expiring under the default `ALL_INPUTS_CHANGED`
  trigger policy. Both were independently reproduced by hand before and
  after fixing, fixed in `snapshot.py` and `session.py` respectively,
  and locked in by `tests/test_multi_instance_post_review_fixes.py` (5
  new tests) plus a necessitated pin update in
  `tests/test_slice_22g_snapshot.py` (same category of fix as MI-B's/
  MI-E's/MI-H's own). Two further findings (Collective's torn-view
  ordering caveat; MI-C's already-disclosed unwired
  `dependency_instances`) were investigated and found not to need a
  code change, addressed by a docstring clarification and by
  re-confirming the existing disclosure respectively. A third bug was
  found afterward while building the example Davi also asked for
  (`examples/multi_instance_fleet_example.py`, new): `render_provenance_
  tree`'s new `[instance=...]` suffix was silently swallowed by Rich's
  own markup parser (`[...]` in a label is markup syntax to Rich, not
  literal text) -- fixed by escaping every label with `rich.markup.
  escape(...)` in `graph.py`. The example itself demonstrates every
  piece of the mechanism end to end (InstanceKey/feed_instances,
  per-instance firing and NodeMemory, Broadcasting including correctly-
  expiring freshness, Collective dependencies via a deliberately
  separate FleetTick to avoid a torn read, instance removal,
  `Snapshot.instances()`, and observability with `instance_id`) and runs
  successfully end to end. 363 passed, 1 skipped (up from 357 before
  this whole review round), ruff clean.
