"""
Focused tests for Slice 2D (NodeContext runtime: `ctx.memory` +
`ctx.last_output`).

No target-architecture-contract test is expected to move for this slice
(docs/refactor_priority_order.md's Slice 2D row: "No target test moves
alone (see 2E; `ctx.last_output` needs a commit to report)"). Both
`test_session_instances_isolate_node_memory` and
`test_last_output_exposes_latest_committed_domain_value` call
`session.feed(...)`/`session.push()`, which does not exist until Slice 2E's node-execution
firing pipeline -- confirmed by reading both test bodies in full before
implementation. This file is Slice 2D's dedicated focused verification,
following the same rationale used for Slices 1A-1E, 2A, 2B, and 2C.

Covers exactly the ownership/isolation/representation properties this
slice establishes:

    1. `NodeSession.memory` is lazily instantiated from the declared
       `MemoryType` via a zero-argument construction, and memoized (same
       object identity, mutable in place) across repeated accesses on the
       same `NodeSession`.
    2. Two different `Session`s (even from the same `Flow`, for the same
       node) never share a memory instance -- `NodeMemory` is scoped to
       `Session x NodeSession` (architectural_invariants.md #14, #16), a
       direct structural consequence of Slice 2B's `NodeSession`
       isolation.
    3. `FlowNode` and `Flow` store no memory of their own.
    4. `ctx.last_output` is `None` before any commit exists (there is no
       commit mechanism in this slice at all).
    5. `NodeContext` exposes only `.memory`/`.last_output` -- no
       `Session`/`Flow`/`FlowNode`/`NodeSession`/repository/bus access, and no
       back-reference to anything internal.
    6. `NodeSession.memory`/`.last_output`/`.context` raise for a node
       that declares no `NodeContext` parameter at all.
    7. No execution, commit, or repository capability was introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import pytest


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


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


def test_node_session_memory_is_instantiated_from_declared_memory_type():
    flow, track = _make_flow_with_tracker()
    session = flow.session()

    memory = session.node_session(track).memory

    assert isinstance(memory, TrackerMemory)
    assert memory.previous_confidence is None


def test_node_session_memory_is_memoized_across_accesses():
    flow, track = _make_flow_with_tracker()
    session = flow.session()
    node_session = session.node_session(track)

    first = node_session.memory
    first.previous_confidence = 0.5
    second = node_session.memory

    assert first is second
    assert second.previous_confidence == 0.5


def test_ctx_memory_mutation_persists_across_context_accesses():
    flow, track = _make_flow_with_tracker()
    session = flow.session()
    node_session = session.node_session(track)

    node_session.context.memory.previous_confidence = 0.7

    assert node_session.context.memory.previous_confidence == 0.7


def test_two_sessions_from_the_same_flow_have_independent_memory():
    flow, track = _make_flow_with_tracker()

    first_session = flow.session()
    second_session = flow.session()

    first_memory = first_session.node_session(track).memory
    second_memory = second_session.node_session(track).memory

    assert first_memory is not second_memory

    first_memory.previous_confidence = 0.1
    second_memory.previous_confidence = 0.8

    assert first_session.node_session(track).memory.previous_confidence == 0.1
    assert second_session.node_session(track).memory.previous_confidence == 0.8


def test_repeated_session_node_session_lookup_shares_memory():
    # NodeSession memoization (Slice 2B) means repeated session.node_session(...)
    # lookups on the same Session return the same NodeSession, and therefore
    # the same memory.
    flow, track = _make_flow_with_tracker()
    session = flow.session()

    session.node_session(track).memory.previous_confidence = 0.3

    assert session.node_session(track).memory.previous_confidence == 0.3


def test_flow_node_stores_no_memory():
    flow, track = _make_flow_with_tracker()
    flow_node = None
    for candidate in flow.flow_nodes:
        if candidate.definition.function is track:
            flow_node = candidate
    assert flow_node is not None

    before = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    session = flow.session()
    session.node_session(track).memory.previous_confidence = 0.9
    session.node_session(track).context

    after = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    assert before == after
    assert not hasattr(flow_node, "memory")
    assert not hasattr(flow_node, "last_output")
    assert not hasattr(flow_node, "context_instance")


def test_flow_stores_no_memory():
    flow, track = _make_flow_with_tracker()

    before = dict(vars(flow))

    session = flow.session()
    session.node_session(track).memory.previous_confidence = 0.4

    after = dict(vars(flow))

    assert before.keys() == after.keys()
    for key in before:
        assert before[key] is after[key], (
            f"Flow.{key} changed identity after NodeContext memory access -- "
            "Flow must own no Session-specific mutable state"
        )
    assert not hasattr(flow, "memory")
    assert not hasattr(flow, "node_memory")


def test_ctx_last_output_is_none_before_any_commit():
    flow, track = _make_flow_with_tracker()
    session = flow.session()

    assert session.node_session(track).last_output is None
    assert session.node_session(track).context.last_output is None


def test_node_context_exposes_no_internal_infrastructure():
    flow, track = _make_flow_with_tracker()
    session = flow.session()

    ctx = session.node_session(track).context

    assert not hasattr(ctx, "session")
    assert not hasattr(ctx, "flow")
    assert not hasattr(ctx, "flow_node")
    assert not hasattr(ctx, "node_session")
    assert not hasattr(ctx, "repository")
    assert not hasattr(ctx, "bus")
    assert not hasattr(ctx, "outpost")
    assert not hasattr(ctx, "_node_session")
    assert not hasattr(ctx, "_session")


def test_node_session_memory_and_context_raise_for_a_node_without_node_context():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    node_session = session.node_session(produce)

    assert not hasattr(node_session, "memory")
    assert not hasattr(node_session, "context")
    assert not hasattr(node_session, "last_output")

    with pytest.raises(AttributeError):
        node_session.memory

    with pytest.raises(AttributeError):
        node_session.context

    with pytest.raises(AttributeError):
        node_session.last_output


def test_node_session_context_returns_a_node_context_instance():
    from reed.composition.node.node_context import NodeContext

    flow, track = _make_flow_with_tracker()
    session = flow.session()

    ctx = session.node_session(track).context

    assert isinstance(ctx, NodeContext)


def test_node_context_cannot_be_constructed_without_memory_and_last_output():
    from reed.composition.node.node_context import NodeContext

    with pytest.raises(TypeError):
        NodeContext()  # type: ignore[call-arg]


def test_no_execute_fire_or_context_commit_wrap_unwrap_capability_was_introduced():
    # Slice 2E legitimately adds Session.publish and NodeSession.commit as
    # the real firing/commit path, making the two assertions that
    # pinned their absence stale by construction -- removed here, the
    # same Test Integrity Rule precedent already applied in Slices 2B
    # and 2D (see docs/refactor_state.md). Every other assertion below
    # is still true after Slice 2E (NodeSession.execute/.fire and
    # NodeContext.commit/.wrap/.unwrap were not introduced by this
    # slice) and is kept unchanged.
    flow, track = _make_flow_with_tracker()
    session = flow.session()
    node_session = session.node_session(track)

    assert not hasattr(node_session, "execute")
    assert not hasattr(node_session, "fire")
    ctx = node_session.context
    assert not hasattr(ctx, "commit")
    assert not hasattr(ctx, "wrap")
    assert not hasattr(ctx, "unwrap")
