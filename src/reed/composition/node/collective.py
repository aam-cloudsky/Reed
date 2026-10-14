"""
Collective marker (Slice MI-H, docs/refactor/multi_instance_execution_plan.md
Section 5 item 8 -- Collective dependencies).

Scope for this slice (.claude/reed-refactor/run-MI-H-*/slice_contract.yaml):

    A node declares a consumed parameter as collective -- resolving, at
    firing time, to the currently known set of instances of that domain
    type (`reed.synchronization.artifact_repository.ArtifactRepository.
    get_all_artifact_records`, Slice MI-B), rather than one scalar
    last-known value -- by annotating it `Annotated[T, Collective]`
    instead of plain `T`.

`Collective` is detected by annotation shape, exactly mirroring the
precedent `Sampled` already established (Slice 21B,
`reed.composition.node.sampled.Sampled`): detected in
`reed.composition.node.domain_signature.DomainNodeSignatureParser` via
`typing.get_type_hints(..., include_extras=True)` plus
`typing.get_origin(annotation) is Annotated` /
`typing.get_args(annotation)`, independent of whether `Sampled` is also
present in the same metadata tuple.

This slice's own SliceContract records, and discloses rather than
silently assumes, a genuine fork: the plan document's own prose describes
this as "a node declared with `Collection[T]`", which could instead have
been read as detecting the bare `Collection[T]` / `collections.abc.
Collection[T]` generic origin directly. `Annotated[T, Collective]` was
chosen instead, for consistency with the one existing convention this
codebase already has for this exact kind of thing (orthogonal, additive,
annotation-shape-detected parameter metadata), and to avoid colliding
with a node that legitimately consumes a literal collection-shaped
domain type as a single scalar artifact.

A `Collective`-marked consumed parameter's `ArtifactDescriptor.input_role`
is always `InputRole.SAMPLED` (see `domain_node_description.py`): its own
arrival must never by itself make its node eligible to fire (plan
document: "evaluated for eligibility under its own, collective readiness
rule, distinct from per-instance `_is_eligible_to_fire`"), so a
collective-consuming node needs at least one ordinary TRIGGERING
consumed type to ever fire automatically through the cascade --
`ArtifactDependencyGraph.register(...)`'s existing `ZeroTriggeringInputs
Error` (Slice 21D) already enforces this, unchanged.

Ordering caveat, surfaced by an independent post-MI-J review and worth
stating explicitly rather than leaving implicit in "a straightforward,
static read of repository state at that moment" above: that static read
happens at the exact instant the consuming node fires, so its result can
be a torn/incomplete view of "every instance that will eventually exist
this propagation" if some instances of `T` are still being produced by
OTHER nodes later in the SAME `push()` call's cascade (FIFO order is not
guaranteed to commit every instance of `T` before this node's own
TRIGGERING partner makes it eligible). This is not a new gap this slice
introduces; it is the direct consequence of Quiescence's own already-
documented resolution (docs/refactor/multi_instance_state.md, Slice
MI-I): "whether a collective read sees every instance that will exist
this tick is caller-controlled." A caller who needs a stable, complete
Collective read should ensure every instance of `T` is committed via
`feed_instances(...)` BEFORE calling `push()`, rather than relying on
other nodes to produce those instances mid-cascade within the same
`push()` call.
"""

from __future__ import annotations


class Collective:
    """
    Marker for `Annotated[T, Collective]` on a consumed node parameter.

    Carries no state and is never constructed; its only role is to be
    recognized, by identity, in the metadata tuple of an `Annotated[...]`
    type hint. At firing time, a `Collective`-marked parameter's value is
    the currently known collection of instances of `T` (a `tuple[T,
    ...]`, resolved from `ArtifactRepository.get_all_artifact_records`),
    not one scalar `T` value.
    """
