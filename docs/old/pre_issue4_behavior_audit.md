# Pre-Issue-4 Foundational Behavior Audit (2026-09-12)

This document is repository authority (per `docs/refactor_agent_protocol.md`'s
Context Loading Rule): future agents must derive the automatic-propagation
requirement from this document, not from conversation history.

## Why this audit exists

The project owner rejected an earlier `ISSUE_4_COMPLETE` declaration (made
after Milestone 2/Slices 2A-2G) as premature: passing the documented
target-architecture-contract tests is necessary but not sufficient for Issue
#4. Issue #4 replaces foundational Reed composition/execution architecture,
so completion requires that Reed work end-to-end as a real dataflow system,
not merely that the new abstractions exist in isolation.

## Method

Investigated the legacy `@flow`/`@node` implementation as of commit
`fd14a37` ("Checkpoint before refactorrefactor.", the last commit before
Issue #4's work began): `src/reed/composition/node/node.py`,
`src/reed/composition/flow/flow.py`, `src/reed/synchronization/logistics.py`,
`src/reed/synchronization/depot.py`,
`src/reed/composition/node/propagation_policy.py` (all via `git show
fd14a37:<path>`), compared against the current implementation through
Slice 2G.

## Legacy mechanism (for context, NOT to be resurrected verbatim)

Each legacy `Node` owned an `Outpost` (a per-node Depot-synchronized
mailbox) subscribed to the shared `Bus`. Setting any `Parcel` type into the
shared `Depot` broadcast a `DepotUpdate`; every subscribed `Outpost` updated
its fields, recomputed a dirty-flag `Status`, and called back into
`Node._on_status_changed(status)`, which evaluated `Node._should_run(status)`
against the node's `PropagationPolicy` (`ANY_DEPENDENCY_CHANGED` /
`ALL_DEPENDENCIES_CHANGED` / `MANUAL`) and, if eligible, called
`Node.process()`: built arguments from currently-available dependency
values, called the function, and wrote the result back into the Depot,
re-triggering the same cycle for whatever depended on the new value. This
was a complete, working, automatic, message-driven, multi-hop, dirty-flag
propagation engine, with fan-out (one write broadcasts to every subscriber)
and join (`ALL_DEPENDENCIES_CHANGED`) support.

## Inventory

| Capability | Classification (as of Slice 2G) | Notes |
|---|---|---|
| Automatic single-hop propagation | **MISSING / REGRESSED** | Legacy: automatic via Outpost/Depot broadcast. New (through 2G): `Run.publish(...)` requires the caller to retrieve the committed value and republish it manually. |
| Automatic multi-hop propagation | **MISSING / REGRESSED** | Same mechanism, transitively. |
| Fan-out (one artifact, multiple consumers) | **MISSING / REGRESSED** | `Run.publish` (2E) explicitly requires exactly one matching FlowNode and raises `ValueError` for more than one -- fan-out is currently impossible through `publish`, not merely manual. |
| Multi-input join (`ALL_DEPENDENCIES_CHANGED`/`ALL_INPUTS_CHANGED`) | **MISSING / REGRESSED** | `TriggerPolicy.ALL_INPUTS_CHANGED` exists as composition metadata (1E) but nothing evaluates it; `Run.publish` also rejects any FlowNode with more than one consumed artifact type, so a join node cannot fire through `publish` at all today. |
| `TriggerPolicy` actually gating execution | **MISSING / REGRESSED** | Legacy had real gating (`_should_run`). New: `TriggerPolicy` is inert composition-time metadata; `architectural_invariants.md` #18-20 already separates "dirty state alone does not decide eligibility" from "TriggerPolicy evaluates that eligibility" -- the second half was never implemented. |
| Dependency/runtime dirty-state tracking | RE-EXPRESSED (partially) | Legacy: per-Outpost `Status`/`Sentinel`. New: `ArtifactDependencyGraph` (1D) tracks producer/consumer relationships at *composition* time only; no per-Run runtime version/dirty tracking exists yet. |
| Per-node local memory across firings | RE-EXPRESSED (new concept, not a port) | `NodeContext`/`NodeMemory` (2D) has no legacy analogue; correctly implemented already. Out of scope for this specific regression. |
| Last-produced-output visibility | RE-EXPRESSED | Legacy `Node.output_result` -> new `NodeRuntime.last_output` (2D/2E). Equivalent, correctly re-expressed. |
| Post-produce callback (`on_output`) | RE-EXPRESSED (new, additive) | No legacy analogue; a genuine improvement (2F). |
| Callback-failure isolation | RE-EXPRESSED (new) | `run.callback_failures` (2F); no legacy analogue. |
| Unique-producer-per-type constraint | PRESERVED | Legacy: implicit in Outpost schema roles. New: `ArtifactDependencyGraph.DuplicateArtifactProducerError` (1D) -- explicit, arguably stronger. |
| Self-flow rejection | PRESERVED | New: `ArtifactDependencyGraph.SelfFlowError` (1D) + signature-level validation (1A). |
| Repeated updates / re-firing on new data over a Run's lifetime | **MISSING / REGRESSED** | Legacy: an Outpost re-fires on every new qualifying dirty value, arbitrarily many times. New: `Run.publish` fires exactly once per call, one node, no "this changed again" notion beyond calling `publish` again by hand. |
| Stateful firing serialization | PRESERVED (new safety property) | `NodeRuntime.firing_lock` (2G); no legacy analogue to compare against (legacy had no concurrency model at the Node level). |
| Transactional/rollback semantics on node failure | OUT OF SCOPE (both eras) | Neither legacy nor new defines a rollback protocol; `docs/node_context_decision.md`'s "Transaction Semantics" is explicitly still open in both eras. Not a regression. |
| Class/module vocabulary (`Depot`, `Outpost`, `Logistics`, `DepotMessages`, decorators, public exports) | OUT OF SCOPE for this audit, IN SCOPE for Milestone 3 | Naming/infrastructure, not behavior; `docs/refactor_priority_order.md` places this in Milestone 3 by design. |

## Conclusion

The single largest, clearly-established regression is automatic dataflow
propagation itself, including fan-out, joins, and `TriggerPolicy` actually
gating execution. No accepted architectural decision says this was
intentionally dropped; on the contrary, `docs/flow_composition_implementation_basis.md`
lists "per-node trigger policy configuration" as part of Issue #4's own
target public API -- meaningless without something that evaluates the
policy. This capability must be restored and re-expressed through the new
architecture (Flow / Run / FlowNode / NodeRuntime / ArtifactRecord /
ArtifactVersion / ArtifactProvenance / TriggerPolicy / dependency tracking),
not by resurrecting the legacy Outpost/Bus dirty-flag machinery verbatim.
This is the primary work of the slices that follow Milestone 2 in
`docs/refactor_state.md`'s Refactor State Log (Slices 2H onward).
