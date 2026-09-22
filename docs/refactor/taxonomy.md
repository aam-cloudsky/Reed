# Reed Taxonomy

A running index of Reed's own vocabulary, defined precisely and in one place. Each entry is the crisp, single-sentence form of a term as it has been worked out in design conversation, cross-referenced to where the concept is developed at length.

This file is a Reed-specific companion to the general computer-science glossary. `references/ingested/glossary.md` (outside this repository, in the workspace vault) holds established academic and engineering terminology in general use on this project (aliasing, in-place mutation, value semantics, reference semantics, monotonic, provenance, persistent data structure, and others). This file holds Reed-specific terms: the names this project has given to its own concepts.

Entries are alphabetical within each section, so the file stays a reference.

---

## Execution Hierarchy

**Flow**
A composition boundary: the declared set of nodes and their producer/consumer relationships. A Flow carries no execution state of its own. See `docs/refactor/architecture.md`, Architectural Principles.

**Session**
One concrete, long-lived, stateful context for a Flow. A session owns its own authoritative artifact store and persists across as many rounds of `feed()` and `push()` as its caller introduces. See `docs/refactor/session_snapshot_decision.md`.

**Propagation**
One bounded reactive cascade within a Session, seeded by the commits a single `push()` call is responsible for, running until the graph reaches quiescence. A session may contain many propagations over its life.

**Firing**
One execution attempt of one node's participation, inside one propagation.

---

## Nodes and Trigger Policy

**FlowNode**
A node's declared participation in a Flow: what happens when a `NodeDefinition` is added to a composition boundary.

**TriggerPolicy**
`trigger_policy.py`. An execution-eligibility policy of a declared `FlowNode`. It decides, from the pattern of which of a node's *triggering* inputs have changed, whether that node is allowed to fire.

**`TriggerPolicy.MANUAL`**
Never eligible via the cascade. A node under `MANUAL` fires only on explicit request, regardless of how many of its inputs have changed.

**`TriggerPolicy.ALL_INPUTS_CHANGED`**
Fires only once every triggering input has changed since the node's last firing. True join semantics, reset after each firing.

**`TriggerPolicy.ANY_INPUT_CHANGED`**
Fires on any triggering input changing, once every input has at least some known value.

**InputRole**
Whether a declared input is `TRIGGERING` or `SAMPLED`.

**`InputRole.TRIGGERING`**
An input whose arrival is what a node's trigger policy evaluates for eligibility.

**`InputRole.SAMPLED`**
An input whose most recent known value is read when the node fires, but whose own arrival never by itself makes the node eligible.

---

## `feed()`, `push()`, `snapshot()`, `invoke()`

**`Session.feed(value)`**
Introduces a value into the session directly, with origin `EXTERNAL`. Architecturally, `feed()` behaves like a node whose function is the identity transformation, triggered manually rather than by the eligibility cascade, in the same sense that a `MANUAL`-policy node is never eligible via the cascade and fires only on explicit request. It never evaluates eligibility or fires any node on its own (invariant 31).

**`Session.push()`**
Drives every currently dirty node to quiescence: one bounded propagation. Returns `None` (invariant 32).

**`Session.snapshot()`**
Returns the full current repository state as plain domain values, reflecting the moment it is called. A snapshot is an immutable, off-to-the-side observation of state. It stands outside the Session → Propagation → Firing hierarchy: it retains no history of earlier snapshots or pushes (invariant 33).

**`Session.invoke(value)`**
`feed()`, then `push()`, then `snapshot()`, in one call. Makes the ordering of change, propagation, and observation explicit at the API boundary.

---

## Artifact Model

**ArtifactRecord**
The single, identity-stable record Reed holds for one artifact identity. It is mutated in place on each commit (`ArtifactRecord.advance()`); the same object persists in the repository for a type's whole lifetime.

**ArtifactVersion**
One committed instance of an artifact's value. Always derived from that type's current `ArtifactRecord` in the repository, `.next()` if one exists, else `ArtifactVersion.initial()`.

**ArtifactOrigin**
Which of exactly two sources produced a given committed version: `NODE` (a participation's own firing) or `EXTERNAL` (a value fed directly into the session). Every commit sets it explicitly; there is no default and no third, unset value.

**Provenance**
Metadata recorded alongside a committed version: which node produced it (absent for an externally fed version) and which versions of its own inputs it was produced from.

**DuplicateArtifactProducerError**
Raised when a Flow would give one artifact type more than one declared producer node. `Session.feed()` is exempt from this check (invariant 30): it may commit a value for a type that already has a declared producer, because it behaves as an identity-function feed rather than a second producer.

---

## General CS Terms in Active Use

These are defined at length in `references/ingested/glossary.md`. Restated here at the one-sentence grain this file uses, for quick lookup during design conversation:

**Aliasing**
Two references pointing to the same underlying object, so a mutation through one is visible through the other.

**In-place mutation**
Changing an object's state without replacing the object itself; the object's identity persists across the change. This is how `ArtifactRecord.advance()` works.

**Value semantics**
Copying a value produces an independent object; changes to the copy never affect the original.

**Reference semantics**
Copying a reference produces a second alias to the same object; changes through either reference are visible through both.

**Monotonic**
A quantity that only ever increases (or only ever decreases) over its lifetime, such as an artifact's version number.
