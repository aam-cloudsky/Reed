"""
Focused tests for Slice 2A (Flow / Run separation), including the Slice
2A follow-up correcting Run-scoped repository ownership.

No target-architecture-contract test is expected to move for this slice
or this follow-up (docs/refactor_priority_order.md's Slice 2A row: "No
target test moves alone"; confirmed by reading every one of the six
remaining xfail tests in tests/test_target_architecture_contract.py --
all six require NodeRuntime/commit semantics/callback dispatch/stateful
serialization, none of which exist yet). This file is Slice 2A's
dedicated focused verification, following the same rationale used for
Slices 1A/1B/1C/1D.

Covers exactly the five architectural properties the harness assigned to
the original slice, plus the corrected repository-ownership contract
added by the follow-up:

    1. Flow.run() returns a Run.
    2. Two Flow.run() calls return distinct Run instances.
    3. Run is associated with the originating Flow.
    4. Flow remains reusable (no error, no shared mutable state leak,
       across repeated run() calls, and Flow.add(...) still works
       normally after run() has been called).
    5. Run-specific state is not stored on Flow.
    6. Each Run owns its own repository instance, backed by Depot, and
       two Runs never share repository state or repository identity.
"""

from __future__ import annotations


def test_flow_run_returns_a_run():
    from reed import Flow
    from reed.execution.run import Run

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    run = flow.run()

    assert isinstance(run, Run)


def test_two_flow_run_calls_return_distinct_run_instances():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_run = flow.run()
    second_run = flow.run()

    assert first_run is not second_run


def test_run_is_associated_with_the_originating_flow():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    run = flow.run()

    assert run.flow is flow


def test_distinct_flows_produce_runs_associated_with_their_own_flow():
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b() -> str:
        return "b"

    flow_a = Flow()
    flow_a.add(produce_a)

    flow_b = Flow()
    flow_b.add(produce_b)

    run_a = flow_a.run()
    run_b = flow_b.run()

    assert run_a.flow is flow_a
    assert run_b.flow is flow_b
    assert run_a.flow is not run_b.flow


def test_flow_remains_reusable_across_multiple_runs():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    runs = [flow.run() for _ in range(5)]

    assert len({id(r) for r in runs}) == 5
    assert all(r.flow is flow for r in runs)


def test_flow_add_still_works_after_run_has_been_called():
    # Flow must remain a usable composition object after run() -- calling
    # run() must not put Flow into some execution-only state.
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b() -> str:
        return "b"

    flow = Flow()
    flow.add(produce_a)
    flow.run()

    flow_node = flow.add(produce_b)

    assert flow_node.produced_artifact.domain_type is str


def test_flow_instance_state_is_unchanged_by_run():
    # Flow-owns-no-Run-specific-state, verified structurally: calling
    # run() (repeatedly) must not add or mutate any attribute on the
    # Flow instance itself.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))

    flow.run()
    flow.run()
    flow.run()

    after = dict(vars(flow))

    assert before.keys() == after.keys()
    for key in before:
        assert before[key] is after[key], (
            f"Flow.{key} changed identity after calling run() -- "
            "Flow must own no Run-specific mutable state"
        )


def test_run_publish_capability_was_introduced():
    # Slice 2E legitimately adds Run.publish as the real firing entry
    # point, making this test's original negative assertion
    # (not hasattr(run, "publish")) stale by construction -- corrected
    # here in place, the same Test Integrity Rule precedent already
    # applied in Slices 2B and 2D (see docs/refactor_state.md).
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    assert hasattr(run, "publish")


# --- Slice 2A follow-up: Run-scoped repository ownership -------------------


def test_run_has_a_repository_accessor():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    assert hasattr(run, "repository")
    assert run.repository is not None


def test_run_repository_is_backed_by_depot():
    from reed import Flow
    from reed.synchronization.depot import Depot

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    assert isinstance(run.repository, Depot)


def test_each_run_owns_a_distinct_repository_instance():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_run = flow.run()
    second_run = flow.run()

    assert first_run.repository is not second_run.repository


def test_two_runs_from_the_same_flow_do_not_share_repository_identity():
    # Depot.identity is derived from the Bus it was constructed with;
    # two Runs must each construct their own Bus, so their repositories'
    # identities must differ even though both Runs came from one Flow.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_run = flow.run()
    second_run = flow.run()

    assert first_run.repository.identity != second_run.repository.identity


def test_flow_does_not_own_the_repository():
    # Repository ownership belongs to Run, not Flow -- Flow's own
    # instance state must still contain nothing Run-specific, repository
    # included.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))
    flow.run()
    after = dict(vars(flow))

    assert before.keys() == after.keys()
    assert not hasattr(flow, "repository")
    assert not hasattr(flow, "_repository")


def test_repeated_flow_run_calls_remain_independent_with_distinct_repositories():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    runs = [flow.run() for _ in range(5)]

    repository_identities = {run.repository.identity for run in runs}
    assert len(repository_identities) == 5
