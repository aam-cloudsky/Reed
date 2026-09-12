# NodeContext Previous-Input Access -- Design Proposal

Status: PROPOSED (not implemented; no production code has been changed
for this proposal).

This document records a conceptual design for extending `NodeContext`
with read-only access to the artifact values a Node consumed at its
*previous successful firing*, indexed by artifact type. It follows the
same convention as `docs/node_context_decision.md` and
`docs/parcel_boundary_decision.md`: a decision record, not an
implementation plan. No production code is changed by this document.

---

## 1. Motivation

`NodeContext` currently exposes two things:

```python
ctx.memory        # persistent, private, node-local computational state
ctx.last_output    # the previous successful firing's committed output
```

A Node with `TriggerPolicy.ALL_INPUTS_CHANGED` or
`TriggerPolicy.ANY_INPUT_CHANGED` frequently needs to compare its
*current* inputs against its *previous* inputs -- computing a delta, a
rate of change, or a stability check -- without hand-rolling that
comparison into `ctx.memory` on every such Node. Today the only way to
keep the previous input around is to copy it into `ctx.memory` by hand,
which conflates "the framework's committed record of what this Node
last consumed" with "whatever private state the Node author decided to
keep." The proposed `ctx.last[T]` closes that gap as a first-class,
Reed-owned capability, symmetric with `ctx.last_output`.

---

## 2. Semantic Definition

`ctx.last[T]` means exactly one thing:

> The value of artifact type `T` that this Node's participation
> consumed at its own previous *successful* firing, within this Run.

It explicitly does **not** mean:

> The most recent value of artifact type `T` observed anywhere in the
> Run's authoritative artifact state.

These are different concepts, and the difference is load-bearing. Reed
already propagates every committed artifact to every consumer as it
arrives (Reactive Propagation), and a join Node's consumed values are
recorded as they arrive so that eligibility can be evaluated once every
input is covered. That "arrival bookkeeping" is Repository-adjacent
history -- it can and does contain values the Node itself never
actually saw, because a later arrival overwrote an earlier one before
the Node's trigger policy allowed it to fire. `ctx.last[T]` must be
insulated from that entirely: it is a *firing-scoped* snapshot, taken at
the moment of the Node's own commit, not a *repository-scoped* view of
the latest arrival.

Concretely, for a Node under `ALL_INPUTS_CHANGED`:

```text
Firing #1 consumes Statistics S1, ContainsPython C1 -> produces Analysis A1

Repository then receives, in order: Statistics S2, Statistics S3, ContainsPython C2

Firing #2 consumes Statistics S3, ContainsPython C2 (the values that made it fully
fresh) -> during Firing #2:

    ctx.last[Statistics]     == S1     (not S2 -- S2 was never consumed by a firing)
    ctx.last[ContainsPython] == C1
    ctx.last_output           == A1
```

This is verified against the current propagation mechanism (see
Section 6): the cascade's own arrival-tracking state (`Run`'s per-
`FlowNode` last-known-value bookkeeping, used to decide eligibility and
build a firing's call arguments) is overwritten on every arrival,
*before* eligibility is even checked -- it is exactly the kind of
"repository-adjacent" state `ctx.last` must not be confused with, and
must not be implemented on top of.

---

## 3. Alternatives Considered

**(a) Per-parameter dynamically generated attributes**
(`ctx.last.stats`, `ctx.last_stats`, …). Rejected outright, per the
brief: these would need to be generated from the Node's own function
signature or Flow-participation metadata, at which point either static
discoverability is lost (an attribute pyright cannot see without a
generated stub) or a code-generation step becomes part of Reed's public
contract. Reed's whole artifact model is built on domain **type** as
identity (`architectural_invariants.md` #8); indexing by type rather
than by parameter name is the only option that matches that model
without inventing a second, string-keyed identity scheme.

**(b) An additional injected function parameter per consumed input**
(e.g. `previous_stats: Statistics | None` alongside `stats: Statistics`).
Rejected: this doubles a Node's declared parameter count for no
dataflow reason, and blurs "function arguments = current consumed
artifacts" (a distinction this proposal is explicitly asked to
preserve) by placing historical data in the same parameter list as
live dataflow inputs. It would also require
`DomainNodeSignatureParser` to invent a naming convention to
distinguish "current" from "previous" parameters -- effectively
alternative (a) again, one layer down.

**(c) `ctx.last(Statistics)` as a method, rather than
`ctx.last[Statistics]` via `__getitem__`.** A legitimate alternative;
slightly more explicit than subscript syntax at a small readability
cost. Not recommended only because the brief's desired API is
subscript-based and pyright infers the generic result equally well
either way (verified, Section 6) -- there is no technical reason to
prefer the method form, and the subscript form reads closer to "a
read-only, type-indexed mapping," which is the correct mental model.

**(d) Exposing the full historical chain of previous firings**, not
just the immediately preceding one. Out of scope: nothing in the
motivation calls for more than one step of history, and a full chain
would need its own retention/eviction policy (unbounded per-Run growth)
that this proposal does not need to solve. `ctx.last` as a *one-step*
snapshot is a strictly smaller, easier-to-reason-about feature; a
deeper history capability, if ever wanted, is a separate proposal built
on top of this one, not a reason to withhold this one.

**(e) `ctx.last[T]` returning the internal `ArtifactRecord` (with
provenance, version, etc.) instead of the plain domain value.**
Rejected: this would violate `architectural_invariants.md` #24-#26
directly -- Nodes consume and produce domain values, Reed alone owns
wrapping/unwrapping, and internal runtime infrastructure must not leak
through `NodeContext`. `ctx.last[T]` must return the same kind of thing
`ctx.last_output` already returns: an unwrapped domain value or `None`.

**(f) Backing `ctx.last` with the Run's existing cascade arrival-
tracking state** (the per-`FlowNode` last-known-value bookkeeping used
today to evaluate join coverage and build a firing's arguments).
Rejected, and rejected specifically -- this is the mistake the brief's
worked example exists to rule out. That state is updated on every
arrival, before eligibility is checked, so at any given moment it can
already hold a value the Node has not yet been fired with. `ctx.last`
requires new, distinct state that is only ever written at the moment of
a successful commit -- see Section 6.

---

## 4. Recommended Public API

```python
def merge(
    ctx: NodeContext[AnalysisMemory, Analysis],
    stats: Statistics,
    contains: ContainsPython,
) -> Analysis:

    previous_stats = ctx.last[Statistics]

    if previous_stats is not None:
        delta = stats.word_count - previous_stats.word_count

    if ctx.last_output is not None:
        print("Previous analysis:", ctx.last_output)

    ...
```

`ctx.last` is a small, read-only, type-indexed lookup object (a
"previous-inputs view"), exposing exactly one operation:

```python
class PreviousArtifacts:
    def __getitem__(self, artifact_type: type[T]) -> T | None: ...
```

No `.get()`, no `__iter__`, no `__contains__`, no `.keys()`. This
mirrors the deliberate narrowness the project already applies to
`NodeContext` itself (`architectural_invariants.md` #13, "`NodeContext`
exposes only `memory` and `last_output`" -- amended by this proposal to
also include `last`, see Section 9): a Node already knows, statically,
which types it consumes (they are its own function parameters); `ctx.last`
gives it a lookup for one of those types on demand, not a generic
enumerable store of "whatever Reed happens to be tracking."

**Behavior for a type the Node does not consume** (Question 8/9): raise
an error at access time, rather than returning `None`. Returning `None`
for both "this type has no history yet" and "this type is not even a
declared input of this Node" would collapse two very different
situations -- the first is normal (every Node's first firing), the
second is very likely a bug (a typo, a copy-pasted lookup from a
different Node, a stale reference after a signature change) that would
otherwise silently and permanently return `None` forever. It cannot be
rejected earlier, at Flow-composition time, without static analysis of
a function body's subscript expressions -- a much larger and more
speculative undertaking this proposal does not ask for. Runtime
rejection, on first access, with an error message naming the type that
was looked up and the Node's actual declared consumed types, is the
right place to catch this.

A useful, free consequence of this rule: a Node's own **produced**
type can never be looked up via `ctx.last[...]` (a Node cannot consume
and produce the same artifact type, `architectural_invariants.md` #11),
so `ctx.last[Analysis]` inside `merge` above raises the same "not a
declared input" error rather than silently doing something else. Output
history stays exclusively `ctx.last_output`'s concern, with no
accidental overlap -- Question 12 is answered by construction, not by
extra special-casing.

---

## 5. Typing / Pylance Analysis

The generic-`__getitem__`-over-`type[T]` shape was verified directly
against this project's configured pyright, not assumed from familiarity
with the pattern:

```python
T = TypeVar("T")

class PreviousArtifacts:
    def __getitem__(self, artifact_type: type[T]) -> "T | None": ...

pa: PreviousArtifacts
reveal_type(pa[Statistics])       # Statistics | None
reveal_type(pa[ContainsPython])   # ContainsPython | None

x = pa[Statistics]
if x is not None:
    reveal_type(x.word_count)     # int -- narrowed correctly
```

Result: `0 errors, 0 warnings`, with pyright reporting exactly
`Statistics | None` and `ContainsPython | None` for the two lookups, and
correctly narrowing `x` to plain `Statistics` inside the `is not None`
guard, with **no cast, no explicit annotation, and no `Any` anywhere in
the call site**. This confirms the design sketch in the brief works
exactly as hoped, using only the standard `TypeVar`/`type[T]` generic
mechanism pyright/Pylance already support -- nothing exotic (no
`TypedDict`, no `Protocol` overloads, no per-Node generated stub) is
required.

`NodeContext[MemoryType, OutputType]`'s own two type parameters are
untouched by this proposal: `ctx.last`'s generic behavior comes entirely
from `PreviousArtifacts.__getitem__`'s own per-call `TypeVar`, not from
widening `NodeContext` to a third type parameter. This keeps the
existing public generic signature stable and avoids forcing every
current `NodeContext[Memory, Output]` annotation in the codebase (and
downstream code) to be rewritten.

---

## 6. Firing and Commit Semantics

This is the crux of the design, and the reason alternative (f) above is
explicitly rejected. Tracing the current propagation mechanism directly
(`Run.publish`, `Run._fire`, `NodeRuntime.commit`):

- `Run` already tracks, per `FlowNode`, a "last known value per consumed
  type," used purely to decide join coverage/eligibility and to build a
  firing's call arguments. This bookkeeping is updated **on every
  arrival**, before eligibility is even evaluated -- it can legitimately
  hold a value newer than anything the Node has ever actually been
  fired with. This is Repository-adjacent history, exactly the thing
  Section 2 says `ctx.last` must not be.
- `NodeRuntime` already owns a *firing-scoped* commit boundary: it wraps
  a Node's returned value, commits it into the Run's repository, and
  updates its own `last_output` -- all inside the same successful-
  commit path, and only that path (a Node function that raises never
  reaches this point, so `last_output` is provably untouched by a
  failed firing today).

The correct design extends that *same* commit boundary, not the Run's
arrival bookkeeping. Conceptually:

```text
Current firing
    │
    ├── current function arguments  (this Node's live, current inputs)
    ├── ctx.memory
    ├── ctx.last            <- previous firing's consumed inputs
    └── ctx.last_output      <- previous firing's committed output
    │
    ▼
transformation (the Node function executes)
    │
    ▼
successful commit
    │
    ├── current inputs  -> new ctx.last snapshot
    ├── current output  -> new ctx.last_output
    └── working memory  -> committed memory
```

The Node's own commit boundary (the same point that already updates
`last_output`) captures exactly the domain-typed arguments it was just
called with -- excluding the `NodeContext` parameter itself, which is
never a consumed artifact -- into a new, `NodeRuntime`-owned snapshot.
That snapshot is what `ctx.last` reads from on the *next* firing. Two
concrete consequences fall directly out of reusing this exact boundary,
rather than inventing a new one:

- **A failed firing changes nothing** (Question 3). If the Node
  function raises, execution never reaches the commit step, so neither
  `last_output` nor the new inputs snapshot advance -- for free, with
  no additional logic, mirroring the guarantee `last_output` already
  has today.
- **The first firing sees `None` for every declared input** (Question
  4). The snapshot starts empty (or absent); `ctx.last[T]` for any
  declared `T` returns `None` until this `NodeRuntime`'s first
  successful commit -- exactly like `ctx.last_output`.

### Interaction with TriggerPolicy (Questions 5-7)

`ctx.last` is deliberately orthogonal to *how* a firing became eligible
-- it only cares about *what was consumed the last time this Node
actually fired*, however that firing was triggered:

- **`ANY_INPUT_CHANGED`**: the Node may fire on a single input's arrival
  once every input has at least one value. `ctx.last[T]` for the type
  that just changed reflects the value from the Node's own *previous*
  firing -- not necessarily the immediately preceding repository
  arrival, if more than one arrival of that type happened between two
  firings (the same insulation Section 2's worked example demonstrates
  for `ALL_INPUTS_CHANGED`).
- **`ALL_INPUTS_CHANGED`**: exactly the worked example in Section 2.
  Because the snapshot is taken from the call arguments actually used
  at the moment of commit -- not from the Run's continuously-overwritten
  arrival bookkeeping -- `ctx.last[Statistics]` correctly reflects `S1`,
  not the intervening `S2`.
- **`MANUAL`**: unaffected by how or when a firing is invoked. Whatever
  causes a `MANUAL` Node to fire, `ctx.last` behaves identically to the
  other two policies: it reflects the previous successful firing's
  inputs, full stop. This proposal adds no policy-specific branching to
  `ctx.last` itself -- eligibility and history are, and remain, fully
  separate concerns (`architectural_invariants.md` #18-#20).

---

## 7. Edge Cases

| Case | Behavior |
|---|---|
| Node has never fired successfully | `ctx.last[T]` is `None` for every declared consumed type `T`. |
| `T` is not one of this Node's declared consumed types | Raise a clear error naming `T` and the Node's actual declared types (see Section 4). Never silently return `None`. |
| `T` is this Node's own produced type | Same as above -- rejected as "not a declared input," by construction (`architectural_invariants.md` #11). Use `ctx.last_output` instead. |
| Node's most recent firing failed (raised) | `ctx.last` is unaffected; it still reflects the *last successful* firing (or `None`, if there has never been one). |
| Node has no `NodeContext` parameter at all | `ctx.last` does not exist -- there is no `ctx` to expose it on, matching how `.memory`/`.last_output` already behave for such a Node. |
| Two `Run`s of the same `Flow` | Fully isolated. The snapshot is owned by `NodeRuntime`, which is already scoped to exactly one `(Run, FlowNode)` pair and never shared across `Run`s (`architectural_invariants.md` #14, #16) -- this proposal adds no new sharing surface. |
| Domain value is mutable, and the Node (or caller) mutates it in place after the firing that produced it | Aliasing risk, but not a new one: Reed does not deep-copy domain values anywhere today (`ArtifactRecord.value`, `ctx.last_output`, and the Run's own repository storage all hold direct references). `ctx.last[T]` would hold the same kind of reference `ctx.last_output` already holds for the output side. This proposal does not change Reed's copy posture and should not be asked to solve it alone -- see Section 10. |

---

## 8. Interaction with TriggerPolicy -- Summary

Change/invalidation and execution remain strictly separate
(`architectural_invariants.md` #18-#20), and this proposal does not
touch that boundary at all: `ctx.last` is a purely observational,
read-side addition to what a Node can see *once it has been decided
that it will fire*. It never participates in the decision of whether a
Node fires, and firing eligibility never depends on the contents of
`ctx.last`. This keeps `TriggerPolicy != on_output` and `TriggerPolicy`'s
existing eligibility logic (`Run._is_eligible_to_fire`) completely
untouched by this feature.

---

## 9. Compatibility with Existing Architectural Invariants

Satisfied as-is, no change required:

- `Domain Value != ArtifactRecord`, `Artifact identity != artifact
  version` (#7, #9) -- `ctx.last[T]` returns a plain domain value, never
  a record, version, or provenance object.
- `NodeContext != InputPort` (#12) -- `ctx.last` is a read-only
  historical lookup, not a live dataflow input; it never participates in
  `DomainNodeSignatureParser`'s inferred topology.
- `NodeMemory` belongs to `Run x NodeRuntime`; different Runs must not
  share it (#14, #16) -- the new snapshot lives on `NodeRuntime`,
  identically scoped, by construction.
- Stateful `NodeRuntime` firings are serialized (#17) -- the snapshot is
  only ever written inside the same critical section that already
  updates `last_output`, under the same firing lock; no new concurrency
  mechanism is needed.
- `TriggerPolicy != on_output` (#18-#20) -- untouched, see Section 8.
- `on_output` timing/failure guarantees (#21-#23) -- untouched; this
  proposal does not touch `on_output` dispatch at all.
- Nodes consume/produce domain values only; Reed owns wrap/unwrap (#24,
  #25) -- `ctx.last[T]` is unwrapped exactly like `ctx.last_output`
  already is.

**Requires one explicit, disclosed amendment:**

- Invariant #13 currently reads "`NodeContext` exposes only `memory` and
  `last_output`." This proposal requires widening it to "`NodeContext`
  exposes only `memory`, `last_output`, and `last`." This is a
  deliberate architectural decision this document is asking to make,
  not a violation to quietly work around -- the invariant document
  should be updated at the same time this feature is implemented, and
  not before.

---

## 10. Implementation Implications (for a future slice, not this document)

Sketched conceptually, for whoever eventually implements this, to size
the change -- none of this is implemented now:

- `NodeRuntime` gains one additional piece of firing-scoped state,
  alongside `.memory`/`.last_output`: a mapping from consumed domain
  type to the value consumed at the last successful firing. It is
  populated at exactly the same point `.last_output` already is (inside
  `NodeRuntime`'s commit step), from the same call arguments `Run._fire`
  already builds -- minus the `NodeContext` argument itself, which is
  never a consumed artifact.
- `NodeContext` gains one additional constructed value, `last`, built by
  `NodeRuntime.context` from two plain pieces of data it already has
  available: the snapshot mapping above, and the `FlowNode`'s already-
  known declared consumed types (as a plain `frozenset[type]`, not a
  reference to the `FlowNode` or any other runtime object). This
  preserves the existing, deliberate property that `NodeContext` holds
  no reference back to `NodeRuntime`, `Run`, `Flow`, or any other
  internal infrastructure (#26) -- exactly as `.memory` and
  `.last_output` already don't.
- The lookup object backing `ctx.last` (`PreviousArtifacts` or similarly
  named) is a small, immutable value holder with exactly one method,
  `__getitem__`, raising a clear, named error for a type outside the
  passed-in `frozenset`.
- No change is required to `Run.publish`'s propagation cascade, its
  eligibility logic, its arrival bookkeeping, or `on_output` dispatch --
  this feature is additive to the commit boundary only.

---

## 11. Proposed Tests (conceptual)

1. First firing of a Node with declared consumed types: `ctx.last[T]`
   is `None` for each declared `T`.
2. Single-input Node, two firings: on the second firing, `ctx.last[T]`
   equals exactly the value consumed by the first firing.
3. `ALL_INPUTS_CHANGED` join, reproducing Section 2's worked example
   exactly: assert `ctx.last[Statistics] == S1` and
   `ctx.last[ContainsPython] == C1` during Firing #2, even though `S2`
   was committed to the repository in between.
4. `ANY_INPUT_CHANGED` Node with more than one arrival of the same type
   between two firings: `ctx.last[T]` reflects the previous *firing*'s
   value, not the most recent repository arrival.
5. A firing that raises: assert `ctx.last`, `ctx.last_output`, and
   committed memory are all unchanged afterward (extends the existing
   commit-boundary test pattern already used for `last_output`).
6. `ctx.last[T]` for a `T` the Node does not declare as a consumed type:
   raises the documented error, naming both the looked-up type and the
   Node's actual declared types.
7. Two `Run`s of the same `Flow`, each firing independently: each
   `Run`'s `ctx.last` reflects only its own firing history (extends
   `test_run_instances_isolate_node_memory`'s existing pattern).
8. A static typing check (pyright, not pytest, run the same way this
   project already runs it in CI/slice verification) asserting
   `reveal_type(ctx.last[Statistics])` is `Statistics | None` on a small
   fixture Node.

---

## 12. Architectural Risks

- **Invariant #13 must be amended, not silently bent.** This is a real,
  disclosed change to an accepted architectural document, and should be
  made at the same moment this feature ships, exactly like any other
  ADR-governed change in this project.
- **A second place a domain value's reference is retained.** Every
  `NodeRuntime` now retains one additional reference per declared
  consumed type, for as long as the `NodeRuntime` lives (bounded by
  `Run` lifetime, exactly like `last_output` and repository storage
  already are) -- a negligible, bounded cost, not an unbounded history.
- **Aliasing of mutable domain values is not solved by this proposal**,
  and should not be -- it is a pre-existing property of Reed's entire
  no-deep-copy posture (`ArtifactRecord.value`, `last_output`, and
  repository storage all already share this property today). Solving it
  uniformly, if ever needed, is a separate, larger proposal that would
  touch all of these together, not something `ctx.last` should attempt
  in isolation.
- **Temptation to widen `ctx.last` into a general store.** The narrow
  API recommended in Section 4 (typed `__getitem__` only, no iteration,
  no `.get()`) is a deliberate guard against `ctx.last` drifting into a
  service-locator-shaped object over time. Any future request to add
  `.get()`, iteration, or membership testing to `ctx.last` should be
  treated as a new proposal, evaluated against this same narrowness
  principle, not a natural extension granted for free.

---

## 13. Recommendation

```text
ACCEPT
```

The proposed abstraction is architecturally sound and consistent with
Reed's existing model: artifact type as semantic identity, one producer
per type per Flow, domain values (never records) at the Node boundary,
and a firing-scoped commit boundary that already exists and only needs
to be extended, not reinvented. The generic `__getitem__`-over-`type[T]`
mechanism was verified, not assumed, to give pyright/Pylance exactly the
inference the brief asked for, with no casts and no per-Node generated
stubs. The one required architectural change -- widening invariant #13
to include `last` alongside `memory` and `last_output` -- is small,
explicit, and consistent with how this project has always handled
`NodeContext`'s deliberately narrow public surface: extend the
invariant deliberately when the capability genuinely earns its place,
never bend it silently.

Implementation is a future slice, gated on this document being reviewed
and accepted, per the brief. No production code has been changed to
produce this document.
