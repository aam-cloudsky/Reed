"""
Focused tests for Slice 2B (NodeRuntime ownership).

No target-architecture-contract test is expected to move for this slice
(docs/refactor_priority_order.md's Slice 2B row: "No target test moves
alone"; confirmed by reading every one of the six remaining xfail tests
in tests/test_target_architecture_contract.py -- the one that reaches
`NodeRuntime` at all, `test_run_instances_isolate_node_memory`, also
requires `ctx.memory` and `.publish(...)`, both Milestone 2D/2E). This
file is Slice 2B's dedicated focused verification, following the same
rationale used for Slices 1A-1E and 2A.

Covers exactly the ownership/identity properties this slice establishes:

    1. `run.node_runtime(node)` returns a `NodeRuntime`.
    2. The returned `NodeRuntime` references the `FlowNode` for `node`
       and the `Run` it was materialized from.
    3. Repeated calls on the same `Run` for the same node return the
       same `NodeRuntime` instance (materialization is stable within a
       `Run`).
    4. Two different `Run`s -- even created from the same `Flow` --
       never share a `NodeRuntime`, for the same node or otherwise.
    5. `FlowNode` acquires no Run-specific mutable execution state.
    6. `Flow` acquires no `NodeRuntime` ownership.
    7. `NodeRuntime` has no execution capability yet (boundary, not
       runtime).
"""

from __future__ import annotations

import pytest


def test_run_node_runtime_returns_a_node_runtime():
    from reed import Flow
    from reed.execution.node_runtime import NodeRuntime

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    node_runtime = run.node_runtime(produce)

    assert isinstance(node_runtime, NodeRuntime)


def test_node_runtime_references_its_flow_node_and_run():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow_node = flow.add(produce)
    run = flow.run()

    node_runtime = run.node_runtime(produce)

    assert node_runtime.flow_node is flow_node
    assert node_runtime.run is run


def test_repeated_node_runtime_calls_on_the_same_run_return_the_same_instance():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    first_lookup = run.node_runtime(produce)
    second_lookup = run.node_runtime(produce)

    assert first_lookup is second_lookup


def test_two_runs_from_the_same_flow_do_not_share_a_node_runtime():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_run = flow.run()
    second_run = flow.run()

    assert first_run.node_runtime(produce) is not second_run.node_runtime(produce)


def test_distinct_nodes_in_the_same_run_get_distinct_node_runtimes():
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b(value: int) -> str:
        return str(value)

    flow = Flow()
    flow.add(produce_a)
    flow.add(produce_b)
    run = flow.run()

    assert run.node_runtime(produce_a) is not run.node_runtime(produce_b)


def test_node_runtime_raises_for_a_function_not_registered_on_the_flow():
    from reed import Flow

    def produce() -> int:
        return 1

    def unregistered() -> int:
        return 2

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    with pytest.raises(ValueError):
        run.node_runtime(unregistered)


def test_flow_node_acquires_no_run_specific_state_from_node_runtime():
    # FlowNode is a frozen dataclass (Slice 1C/1E) -- calling
    # run.node_runtime(...) must not add any attribute to it or change
    # its identity/equality.
    from reed import Flow
    from dataclasses import fields

    def produce() -> int:
        return 1

    flow = Flow()
    flow_node = flow.add(produce)

    before = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    run = flow.run()
    run.node_runtime(produce)
    run.node_runtime(produce)

    after = {field.name: getattr(flow_node, field.name) for field in fields(flow_node)}

    assert before == after


def test_flow_instance_state_is_unchanged_by_node_runtime():
    # Flow-owns-no-Run-specific-state (already covered for run() itself
    # in Slice 2A) must still hold once NodeRuntime lookups happen.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))

    run = flow.run()
    run.node_runtime(produce)

    after = dict(vars(flow))

    assert before.keys() == after.keys()
    for key in before:
        assert before[key] is after[key], (
            f"Flow.{key} changed identity after run.node_runtime(...) -- "
            "Flow must own no Run-specific mutable state"
        )
    assert not hasattr(flow, "node_runtime")
    assert not hasattr(flow, "_node_runtimes")


def test_node_runtime_has_no_repository_or_execution_capability_yet():
    # NodeRuntime remains an ownership boundary with no repository or
    # execution access as of this slice (unchanged by Slice 2C/2D).
    # `context`/`memory`/`last_output` (Slice 2D) now exist as real
    # properties on NodeRuntime -- see
    # tests/test_slice_2d_node_context.py for their dedicated
    # coverage, including
    # test_node_runtime_memory_and_context_raise_for_a_node_without_node_context,
    # which is the direct successor to this original test's
    # `not hasattr(node_runtime, "memory"/"context"/"last_output")`
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
    run = flow.run()

    node_runtime = run.node_runtime(produce)

    assert not hasattr(node_runtime, "repository")
    assert not hasattr(node_runtime, "execute")
