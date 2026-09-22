# Issue #22 Architectural Decision — Session, `feed`/`push`/`snapshot`, and unified artifact versioning

This document records the architectural decision for issue #22
(`22-a-wave-batched-held-inputs-with-a-single-coherent-propagation-and-a-queryable-result`),
building on the Sampled Inputs work from issue #21 (`InputRole`, `TriggerPolicy`,
already merged, `934b9e0`). It supersedes the "Wave" shape sketched in the original
uploaded proposal and in `references/ingested/issue-22-wave-artifactrecord-exposure-decision.md`
(that document's §5 treated the `Run`→`Session` rename as out of scope; that has since
been decided as in scope and is recorded here instead).

It is the authoritative source for the `run-22*` slice sequence under
`.claude/reed-refactor/`. Where this document and the SliceContracts disagree, this
document wins; the contracts should be corrected to match it, not the reverse.

## 1. Motivation

`Run.publish(value)` (and `publish_many`) has two problems this issue fixes:

1. Its return value is narrow and ad hoc — callers who need "what did propagation
   actually produce, including several hops downstream" fall back to
   `run.repository.get_artifact_record(...)`, an escape hatch that leaks
   `ArtifactRecord` (Reed's internal execution-side wrapper) into caller code.
2. A `publish()`-fed root value never itself becomes a versioned, provenance-tracked
   `ArtifactRecord` in the repository — it is asymmetric with values produced by node
   firings, which always do.

## 2. Decision

Replace `publish()`/`publish_many()` with three explicit, single-purpose operations on
a renamed `Session` (was `Run`), plus a read-only `Snapshot` (was the proposal's `Wave`)
for querying the result:

```text
Flow.add(...)                    # declared composition, unchanged
session = flow.session()         # was flow.run()

session.feed(value)              # record one input; does not fire anything
session.push()                   # -> None. fire eligible nodes to quiescence
snapshot = session.snapshot()    # -> Snapshot: full current repository state
```

`feed`, `push`, and `snapshot` are orthogonal and independently useful (feed several
values, then push once; push, then take a snapshot at leisure) rather than one call
that does all three. `session.invoke(value)` is provided as sugar for the common
single-value case: `feed` + `push` + `snapshot`.

## 3. Nomenclature

| Current name | New name |
|---|---|
| `Run` | `Session` |
| `Flow.run()` | `Flow.session()` |
| `NodeRuntime` | `NodeSession` (+ accessor `session.node_session(fn)`, was `node_runtime(fn)`) |
| — | `Session.feed(value)` |
| — | `Session.push()` |
| — | `Session.snapshot() -> Snapshot` |
| `publish()` / `publish_many()` | removed |
| — | `Snapshot` (was the proposal's `Wave`) |
| `ArtifactProvenance.producer` alone as origin signal | `ArtifactProvenance.origin: ArtifactOrigin` (new field, alongside existing `producer`) |
| — | `ArtifactOrigin` (enum: `NODE`, `EXTERNAL`) |
| — | `ArtifactRecord.advance(value, ...)` |

`ArtifactProvenance` and `ArtifactOrigin` keep the `Artifact` prefix. Every class in
this domain (`ArtifactRepository`, `ArtifactRepositoryId`, `ArtifactRole`,
`ArtifactDescriptor`, `ArtifactDependencyGraph`, `ArtifactVersion`, `ArtifactRecord`)
already carries it without exception, and `src/reed/observability/` already has its own
`Provenance*` family (`ProvenanceEvent`, `ProvenanceStore`, `ProvenanceGraphNode`)
describing a different thing — the observability/persistence layer, not an artifact's
own lineage object. A bare `Provenance` would collide with that name space without
being related to it.

## 4. `feed()` is a node

`Session.feed(value)` is modeled architecturally as **a node whose function is the
identity, triggered manually instead of by the eligibility cascade.** Concretely:

- It performs the same bookkeeping `Run._record_input` performs today: updates
  `_last_known_values` for each consuming `FlowNode`, marks `_fresh_since_last_firing`
  for `TRIGGERING`-role edges only. It never itself evaluates eligibility or fires a
  node — that remains `push()`'s job.
- It additionally commits a real, versioned `ArtifactRecord` into the repository,
  tagged `origin=EXTERNAL`, through the same shared commit path a node firing uses
  (§6). This closes the asymmetry in §1.2: a fed root value now becomes a
  provenance-tracked record like any other.
- It does **not** participate in the declared `Flow`/`ArtifactDependencyGraph`
  composition graph — it is a `Session`-level runtime write path, not a
  `Flow.add(...)`-registered `FlowNode`. This is why it is exempt from
  `DuplicateArtifactProducerError` (invariant 10): that check guards *declared* graph
  producers against each other; `feed()` was never a declared graph participant.
- It is deliberately allowed to write to a domain type that already has a registered
  producer node. This is an intentional escape hatch: an external caller can
  override/inject a value and let it propagate downstream via the normal cascade
  (`push()`) without forcing the whole upstream subgraph to re-execute just to
  re-derive that one value.
- Because it shares the commit path a node firing uses, it also fires the same
  observability hooks a firing does: a generated-provenance event, a trace event, and
  `on_output` dispatch. This is a genuine behavior change from today's `publish()`,
  which fires none of these for a root-published value.

## 5. `push()` and `snapshot()`

`Session.push()` runs the same eligibility → fire → cascade-to-quiescence loop
`Run.publish()`'s `while pending:` loop runs today, seeded by every `FlowNode` that
received a `feed()` since the last `push()` (instead of by one value's direct
consumers). It returns `None` — strictly side-effecting. It does not return a
`Snapshot`; that is `snapshot()`'s job, called separately.

`Session.snapshot()` reads the *full* current state of the repository — every type
currently committed, not scoped to one `push()` call — and returns an immutable
`Snapshot` exposing plain domain values only, never `ArtifactRecord`:

```python
class Snapshot:
    def get(self, domain_type: type, default: object = None) -> object: ...
    # mirrors dict.get(k, default) exactly -- never raises

    def __getitem__(self, domain_type: type) -> object: ...
    # mirrors dict[k] exactly -- KeyError if domain_type was never committed
```

There is no automatic history: `snapshot()` always reflects the latest repository
state at the moment it is called. Retrieving "the result of a specific push" means
calling `snapshot()` immediately after that `push()`, before any further `feed()` or
`push()`. Any retention across time is the caller's own responsibility, outside Reed.
`Session.repository` remains the lower-level escape hatch it is today ("latest known
value of X, whenever committed"); `Snapshot` answers "what does the repository look
like right now," not "what did this specific push produce."

## 6. Unified versioning and `ArtifactOrigin`

Both commit paths — a node firing (`NodeSession.wrap()`) and `feed()` — now go through
one shared operation instead of two parallel implementations:

```python
def _commit(self, value: object, *, origin: ArtifactOrigin,
            producer: Optional["NodeSession"] = None) -> ArtifactRecord:
    """On Session. Reads self.repository.get_artifact_record(type(value)).
    If a record already exists for that type, advances it in place
    (ArtifactRecord.advance) and returns it. Otherwise constructs a fresh
    ArtifactRecord at ArtifactVersion.initial() and stores it."""
```

`NodeSession.wrap()` calls it with `origin=ArtifactOrigin.NODE, producer=self`;
`feed()` calls it with `origin=ArtifactOrigin.EXTERNAL, producer=None`.

Version derivation is fully unified: the next version for a type is always derived
from that type's *current* `ArtifactRecord` in the repository (`.next()` if one
exists, `ArtifactVersion.initial()` if not) — never from a private, per-node or
per-type running counter. `NodeSession.wrap()` drops its own private `self._provenance`
field and reads the repository directly, exactly as `feed()` does. This is grounded in
invariant 10 (`DuplicateArtifactProducerError`, at most one *declared* producer per
domain type per `Flow`): that invariant is what makes a single, type-keyed version
source correct for the node-firing case. `feed()`'s exemption from invariant 10 (§4)
is a separate, explicit design choice, not a loophole in this one.

`ArtifactOrigin` has exactly two values:

```python
class ArtifactOrigin(Enum):
    NODE = auto()
    EXTERNAL = auto()
```

No third `PENDING`/`UNSET` value. A not-yet-advanced `ArtifactProvenance`
(`ArtifactVersion.pending()`, version `0`) never becomes a reachable, committed
`ArtifactRecord` anywhere in the system: `repository.get_artifact_record(T)` returning
`None` *is* the representation of "nothing yet." Since both real commit paths always
pass `origin` explicitly the moment they advance (no default), there is no observable
state where a committed record's `origin` is meaningfully unset.
`ArtifactProvenance.advance(...)`'s `origin` parameter is required, keyword-only, with
no default.

`dependencies={}` always for an `origin=EXTERNAL` record — a fed value depends on
nothing.

## 7. `ArtifactRecord` becomes mutable in place

```python
def advance(self, value: object, *, origin: ArtifactOrigin,
            producer: Optional["NodeSession"] = None) -> None:
    if type(value) is not type(self.value):
        raise TypeError(...)  # the record's domain type is the ArtifactRepository's
                               # dict key, fixed at first commit -- it cannot change
                               # across an in-place advance
    self.value = value
    self.provenance.advance(origin=origin, producer=producer)
```

One `ArtifactRecord` object now persists per type for its whole lifetime in the
repository, mutated in place on each commit, rather than being replaced by a new
object each time. This is a deliberate reversal of the invariant
`tests/test_observability_o7b_provenance_version.py::test_earlier_committed_records_keep_their_own_version_after_later_firings`
protects today ("a committed `ArtifactRecord` must not be mutated by a later firing").
That test is rewritten as part of slice 22C, with a comment explaining the change, per
the Test Integrity Rule precedent set during issue #21.

This was verified safe before being decided, not assumed: the two production
(non-test) call sites that read a committed record from the repository
(`_emit_used_provenance_events`, `NodeRuntime.commit`) both extract what they need
(`.version.number` as a plain `int`; `.value` by reference) immediately and
synchronously, and neither holds a long-lived reference to the record object across a
later firing. Nothing in production code depends on old `ArtifactRecord` objects
staying frozen; only the named regression test asserted that behavior, by design, and
is updated to assert the new one instead.

This is an instance of **aliasing** and **in-place mutation** as defined in
`references/ingested/glossary.md`: after this change, every reader that retrieved an
`ArtifactRecord` reference before a later `.advance()` call is aliased to the mutated
object and observes the mutation. Contrast with the previous, replaced-object model,
which gave callers **value semantics** over each retrieved record (a later commit
could not affect an already-retrieved reference). Any future code that needs the old
value-semantics guarantee must copy explicitly (`copy.copy`/`dataclasses.replace`, or
an equivalent), the same way `ArtifactProvenance.copy()` already exists for that
purpose today.

## 8. Target public API (reference)

```python
from reed import Flow, TriggerPolicy, NodeContext, Sampled

flow = Flow()
flow.add(calibrate)                    # declared FlowNode(s), unchanged

session = flow.session()               # was flow.run()

session.feed(CalibrationOffset(0.5))   # SAMPLED for calibrate: recorded, does not trigger
session.feed(RawReading(10.0))         # TRIGGERING: recorded, marks calibrate fresh

session.push()                         # -> None. Evaluates eligibility, fires,
                                        #    cascades to quiescence.

snapshot = session.snapshot()          # -> Snapshot: full current repository state
snapshot.get(CalibratedReading)                 # -> CalibratedReading(...) or None
snapshot.get(CalibratedReading, default_value)  # -> CalibratedReading(...) or default_value
snapshot[CalibratedReading]                     # -> CalibratedReading(...), or KeyError if absent

# Convenience, single-input case:
def invoke(self, domain_value: object) -> "Snapshot":
    self.feed(domain_value)
    self.push()
    return self.snapshot()
```

## 9. Implementation plan

Nine slices under `.claude/reed-refactor/run-22*`, each depending only on the ones
before it (22H split into two sub-steps per the process refinement agreed for this
issue — migrate call sites before deleting `publish()`, rather than one slice doing
both):

1. **22A** — Rename pass: `Run`→`Session`, `Flow.run()`→`Flow.session()`,
   `NodeRuntime`→`NodeSession` (+ accessor), every internal reference. Purely
   mechanical, no behavior change.
2. **22B** — `ArtifactOrigin` enum + `ArtifactProvenance.origin` field (required
   keyword-only at `.advance()`). Update the one current call site
   (`NodeSession.wrap()`) to pass `origin=ArtifactOrigin.NODE`. Purely additive.
3. **22C** — `ArtifactRecord.advance(value, ...)`. Rewrite
   `test_earlier_committed_records_keep_their_own_version_after_later_firings` with an
   explanatory comment. `NodeSession.wrap()` not yet switched over to it in this slice.
4. **22D** — Shared commit path `Session._commit(...)`; `NodeSession.wrap()`
   reimplemented to call it and drop its private `self._provenance`.
5. **22E** — `Session.feed(value)`: existing bookkeeping + `_commit(value,
   origin=EXTERNAL, producer=None)`. No producer guard.
6. **22F** — `Session.push()`: adapt `publish()`'s eligibility→fire→cascade loop,
   seeded by feed-touched nodes. Returns `None`.
7. **22G** — `Snapshot` / `Session.snapshot()` / `Session.invoke()`.
8. **22H-1** — Migrate every internal call site and test to `feed`/`push`/`snapshot`
   (or `invoke`) while `publish()`/`publish_many()` still exist, including
   `examples/sampled_inputs.py`, `examples/new_api.py`,
   `examples/observability_example.py`, `examples/text_analysis_pipeline.py`.
9. **22H-2** — Delete `publish()`/`publish_many()` now that nothing calls them.

Each slice is implemented and independently reviewed before the next starts, following
the same implementer/reviewer discipline used for #21's 21A–21D: the reviewer
independently re-runs the full test suite and ruff, re-verifies any empirical claim in
the implementer's report rather than trusting it, and does not approve on the
implementer's word alone. Slice 22C gets extra scrutiny (broader-than-usual grep for
any other reader of a committed `ArtifactRecord`, including `src/reed/observability/`
and `src/reed/observability/replay.py`) given it is the one slice that deliberately
removes a previously-protected invariant. Every slice's review reconfirms the full
existing test suite passing, not only the new slice-specific tests.

## 10. Non-goals

- No change to `Flow`, `FlowNode`, `TriggerPolicy`, `InputRole`, `Sampled`, or the
  composition-time graph (`ArtifactDependencyGraph`) beyond the `Run`→`Session`
  rename's mechanical touch on `Flow.session()`'s return type.
- No wave-scoped provenance object. Provenance for what a specific `push()` produced
  remains available through the existing OTel tracing/observability path
  (`docs/refactor/observability_design.md` and related), not duplicated onto
  `Snapshot`.
- No history retention inside `Snapshot` or `Session` beyond the single current
  repository state.
- No change to `ArtifactRepository`'s own storage model (still a dict keyed by
  `type(record.value)`, overwrite-on-commit) beyond what `ArtifactRecord.advance()`
  requires of it.

## 11. Full decision log

The complete, turn-by-turn design conversation this document distills — including
alternatives considered and rejected along the way (a parallel `_external_provenance`
structure; reusing `TriggerPolicy.MANUAL` as an origin signal; a `PENDING`/`UNSET`
third `ArtifactOrigin` value; `Wave.records: Mapping[type, ArtifactRecord]`) — is
preserved outside this repository at
`references/ingested/issue-22-wave-session-design-decisions-log.md` for continuity.
This document is the one to follow for implementation; that one is the historical
record of how it was reached.

## 12. Implementation status

**Complete** as of slices 22A-22H-2 (`.claude/reed-refactor/run-22*-20260921T173306Z/`,
final verification at `.claude/reed-refactor/issue22-final-verification/final_review.yaml`).
Every slice in section 9 was implemented and independently reviewed (PASS on every
review); `publish()`/`publish_many()` are removed; the full target API in section 8
works end-to-end; the full regression suite and ruff are green. No git operations were
performed by any agent during this work, per standing instruction -- everything exists
only as uncommitted working-tree changes, left for the maintainer's own review and
commit.
