"""
Focused tests for Slice 2B (NodeSession ownership).

No target-architecture-contract test is expected to move for this slice
(docs/refactor_priority_order.md's Slice 2B row: "No target test moves
alone"; confirmed by reading every one of the six remaining xfail tests
in tests/test_target_architecture_contract.py -- the one that reaches
`NodeSession` at all, `test_session_instances_isolate_node_memory`, also
requires `ctx.memory` and `feed()`/`push()`, both Milestone 2D/2E). This
file is Slice 2B's dedicated focused verification, following the same
rationale used for Slices 1A-1E and 2A.

Covers exactly the ownership/identity properties this slice establishes:

    1. `session.node_session(node)` returns a `NodeSession`.
    2. The returned `NodeSession` references the `FlowNode` for `node`
       and the `Session` it was materialized from.
    3. Repeated calls on the same `Session` for the same node return the
       same `NodeSession` instance (materialization is stable within a
       `Session`).
    4. Two different `Session`s -- even created from the same `Flow` --
       never share a `NodeSession`, for the same node or otherwise.
    5. `FlowNode` acquires no Session-specific mutable execution state.
    6. `Flow` acquires no `NodeSession` ownership.
    7. `NodeSession` has no execution capability yet (boundary, not
       runtime).
"""

from __future__ import annotations

import pytest


def test_session_node_session_returns_a_node_session():
    from reed import Flow
    from reed.execution.node_session import NodeSession

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    node_session = session.node_session(produce)

    assert isinstance(node_session, NodeSession)


def test_node_session_references_its_flow_node_and_session():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow_node = flow.add(produce)
    session = flow.session()

    node_session = session.node_session(produce)

    assert node_session.flow_node is flow_node
    assert node_session.session is session


def test_repeated_node_session_calls_on_the_same_session_return_the_same_instance():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    first_lookup = session.node_session(produce)
    second_lookup = session.node_session(produce)

    assert first_lookup is second_lookup


def test_two_sessions_from_the_same_flow_do_not_share_a_node_session():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_session = flow.session()
    second_session = flow.session()

    assert first_session.node_session(produce) is not second_session.node_session(produce)


def test_distinct_nodes_in_the_same_session_get_distinct_node_sessions():
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b(value: int) -> str:
        return str(value)

    flow = Flow()
    flow.add(produce_a)
    flow.add(produce_b)
    session = flow.session()

    assert session.node_session(produce_a) is not session.node_session(produce_b)


def test_node_session_raises_for_a_function_not_registered_on_the_flow():
    from reed import Flow

    def produce() -> int:
        return 1

    def unregistered() -> int:
        return 2

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    with pytest.raises(ValueError):
        session.node_session(unregistered)


def test_flow_node_acquires_no_session_specific_state_from_node_session():
    # FlowNode is a frozen dataclass (Slice 1C/1E) -- calling
    # session.node_session(...) must not add any attribute to it or change
    # its identity/equality.
    from reed import Flow
    from dataclasses import fields

    def produce() -> int:
        return 1

    flow = Flow()
    flow_node = flow.add(produce)

    before = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    session = flow.session()
    session.node_session(produce)
    session.node_session(produce)

    after = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    assert before == after


def test_flow_instance_state_is_unchanged_by_node_session():
    # Flow-owns-no-Session-specific-state (already covered for session() itself
    # in Slice 2A) must still hold once NodeSession lookups happen.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))

    session = flow.session()
    session.node_session(produce)

    after = dict(vars(flow))

    assert before.keys() == after.keys()
    for key in before:
        assert before[key] is after[key], (
            f"Flow.{key} changed identity after session.node_session(...) -- "
            "Flow must own no Session-specific mutable state"
        )
    assert not hasattr(flow, "node_session")
    assert not hasattr(flow, "_node_sessions")


def test_node_session_has_no_repository_or_execution_capability_yet():
    # NodeSession remains an ownership boundary with no repository or
    # execution access as of this slice (unchanged by Slice 2C/2D).
    # `context`/`memory`/`last_output` (Slice 2D) now exist as real
    # properties on NodeSession -- see
    # tests/test_slice_2d_node_context.py for their dedicated
    # coverage, including
    # test_node_session_memory_and_context_raise_for_a_node_without_node_context,
    # which is the direct successor to this original test's
    # `not hasattr(node_session, "memory"/"context"/"last_output")`
    # assertions for a node like `produce` below that declares no
    # NodeContext parameter at all (those properties correctly raise
    # AttributeError for such a node, so hasattr(...) still reports
    # False for it -- see that test for the explicit, positive
    # assertion of why).
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    node_session = session.node_session(produce)

    assert not hasattr(node_session, "repository")
    assert not hasattr(node_session, "execute")
