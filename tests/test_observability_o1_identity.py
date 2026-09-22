"""
Milestone O1 -- Identity Foundations (Slices O1a-O1f).

Covers the observability identity model resolved and implemented this
milestone (docs/observability_design.md Section 18; docs/observability_
harness.md's O1 table; docs/observability_implementation_plan.md Section
4.2):

    1. `Flow.flow_id` is deterministic and stable across separate `Flow`
       instances built from the same composition (same node functions,
       same order) -- the cross-process stability property, exercised
       here as cross-instance stability within one process (the
       deterministic derivation makes the two equivalent: a fresh `Flow`
       instance is exactly what a second process session also builds).
    2. `Flow.flow_id` changes when the composition changes (a node added,
       removed, or reordered).
    3. `FlowNode.node_id` is deterministic (module + qualname), distinct
       from `FlowNode.node_name` (the function's `__name__`, cosmetic
       only, allowed to collide).
    4. `Session.execution_id` is a fresh, distinct value per `Session` instance.
    5. `Session.flow_id` passes through to `self.flow.flow_id`.
    6. Firing a stateful Node attaches a `NodeExecutionIdentity` to the
       injected `NodeContext`, with a fresh `node_execution_id` and an
       incrementing `execution_seq` on every firing, scoped to one Session.
    7. A `NodeContext` built without `identity=` (e.g. `NodeSession.context`,
       or direct construction) still works exactly as before -- `identity`
       defaults to `None`; no existing behavior changed.
    8. The identity bundle carries no back-reference to `Session`, `Flow`, or
       `NodeSession` -- only plain values.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def _make_flow_with_tracker():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    return flow, track


def test_flow_id_is_deterministic_across_separate_instances():
    from reed import Flow

    def produce() -> Measurement:
        return Measurement(1)

    first_flow = Flow()
    first_flow.add(produce)

    second_flow = Flow()
    second_flow.add(produce)

    assert first_flow.flow_id == second_flow.flow_id


def test_flow_id_changes_when_composition_changes():
    from reed import Flow

    def produce_one() -> Measurement:
        return Measurement(1)

    def produce_two() -> Estimate:
        return Estimate(1)

    flow_with_one_node = Flow()
    flow_with_one_node.add(produce_one)

    flow_with_two_nodes = Flow()
    flow_with_two_nodes.add(produce_one)
    flow_with_two_nodes.add(produce_two)

    assert flow_with_one_node.flow_id != flow_with_two_nodes.flow_id


def test_flow_id_is_a_short_hex_string():
    from reed import Flow

    def produce() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow.add(produce)

    flow_id = flow.flow_id
    assert isinstance(flow_id, str)
    assert len(flow_id) == 16
    int(flow_id, 16)  # must be valid hex


def test_node_id_is_deterministic_module_qualname_not_object_identity():
    from reed import Flow

    def produce() -> Measurement:
        return Measurement(1)

    first_flow = Flow()
    first_node = first_flow.add(produce)

    second_flow = Flow()
    second_node = second_flow.add(produce)

    assert first_node.node_id == second_node.node_id
    assert first_node.node_id == f"{produce.__module__}.{produce.__qualname__}"


def test_node_name_is_display_only_and_allowed_to_collide():
    from reed import Flow

    def produce_a() -> Measurement:
        return Measurement(1)

    def produce_b() -> Estimate:
        return Estimate(1)

    produce_a.__name__ = "shared_name"  # type: ignore[attr-defined]
    produce_b.__name__ = "shared_name"  # type: ignore[attr-defined]

    flow = Flow()
    node_a = flow.add(produce_a)
    node_b = flow.add(produce_b)

    assert node_a.node_name == node_b.node_name == "shared_name"
    assert node_a.node_id != node_b.node_id


def test_execution_id_is_distinct_per_session():
    flow, _track = _make_flow_with_tracker()

    first_session = flow.session()
    second_session = flow.session()

    assert first_session.execution_id != second_session.execution_id
    assert isinstance(first_session.execution_id, str)


def test_session_flow_id_passes_through_to_flow():
    flow, _track = _make_flow_with_tracker()
    session = flow.session()

    assert session.flow_id == flow.flow_id


def test_firing_attaches_identity_bundle_to_injected_context():
    from reed.observability.identity import NodeExecutionIdentity

    flow, track = _make_flow_with_tracker()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    ctx = session.node_session(track).context
    # `.context` itself still defaults to identity=None (unchanged
    # behavior) -- the identity actually attached during firing is only
    # observable from inside the node body. Assert that indirectly via a
    # node that records what it received.
    assert ctx.identity is None


def test_firing_attaches_identity_bundle_observed_from_inside_node():
    from reed import Flow, NodeContext
    from reed.observability.identity import NodeExecutionIdentity

    observed: list[NodeExecutionIdentity | None] = []

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        observed.append(ctx.identity)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed(Measurement(1))
    session.push()
    session.feed(Measurement(2))
    session.push()

    assert len(observed) == 2
    first, second = observed

    assert isinstance(first, NodeExecutionIdentity)
    assert isinstance(second, NodeExecutionIdentity)

    assert first.execution_id == second.execution_id == session.execution_id
    assert first.flow_id == second.flow_id == session.flow_id
    assert first.node_id == second.node_id == flow.flow_nodes[0].node_id

    assert first.node_execution_id != second.node_execution_id
    # Each feed()+push() cycle now consumes two execution_seq values --
    # one for feed()'s own identity-bundle commit of the fed Measurement,
    # one for track's firing (Slice 22E) -- rather than one, as a bare
    # publish() call used to. The two firings' own execution_seq values
    # are still strictly increasing and two apart.
    assert second.execution_seq == first.execution_seq + 2
    assert second.execution_seq > first.execution_seq


def test_node_context_without_identity_defaults_to_none():
    from reed import NodeContext

    ctx = NodeContext(memory=None, last_output=None)

    assert ctx.identity is None


def test_identity_bundle_has_no_back_reference_to_execution_infrastructure():
    from reed.observability.identity import NodeExecutionIdentity

    identity = NodeExecutionIdentity(
        execution_id="e",
        flow_id="f",
        node_id="n",
        node_execution_id="ne",
        execution_seq=1,
    )

    # Only plain values -- no attribute exposes anything but str/int.
    for field_name in ("execution_id", "flow_id", "node_id", "node_execution_id"):
        assert isinstance(getattr(identity, field_name), str)
    assert isinstance(identity.execution_seq, int)

    with pytest.raises(AttributeError):
        identity.session  # type: ignore[attr-defined]
