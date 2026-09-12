"""
Focused tests for Slice 2G (docs/refactor_priority_order.md, Milestone 2,
Slice 2G row; architectural_invariants.md #17, "Stateful NodeRuntime
firings are serialized").

These tests exist alongside
tests/test_target_architecture_contract.py's own
test_stateful_node_runtime_firings_are_serialized because that target
test is single-threaded -- it calls `run.publish_many(...)` sequentially
and never actually exercises concurrent firings, so its
`max_active == 1` assertion would pass even by accident if
`Run.publish(...)` simply never ran two firings at once (which today it
never does). These tests instead verify the real mechanism the
SliceContract requires: a lazily-created `threading.Lock`, one per
state-aware `NodeRuntime`, actually held across the
node-function-call-through-commit window -- and prove, using a real
background thread and a deliberately slow node function, that two
firings of the *same* state-aware `NodeRuntime` cannot overlap even
under genuine concurrency.
"""

from __future__ import annotations

import threading
import time

from reed import Flow, NodeContext, TriggerPolicy


class _Memory:
    pass


class _Input:
    def __init__(self, value: int) -> None:
        self.value = value


class _Output:
    def __init__(self, value: int) -> None:
        self.value = value


def test_state_aware_node_runtime_gets_a_lazily_created_lock():
    def track(ctx: NodeContext[_Memory, _Output], value: _Input) -> _Output:
        return _Output(value.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    node_runtime = run.node_runtime(track)

    # No lock exists until first accessed.
    assert node_runtime._firing_lock is None

    lock = node_runtime.firing_lock
    assert lock is not None
    assert isinstance(lock, type(threading.Lock()))

    # Memoized: repeated access returns the exact same Lock instance.
    assert node_runtime.firing_lock is lock


def test_stateless_node_runtime_gets_no_lock_at_all():
    def produce(value: _Input) -> _Output:
        return _Output(value.value)

    flow = Flow()
    flow.add(produce)
    run = flow.run()

    node_runtime = run.node_runtime(produce)

    assert node_runtime.firing_lock is None
    # Confirm no lock object was ever created as a side effect either.
    assert node_runtime._firing_lock is None


def test_lock_is_held_during_the_node_function_call_and_released_after():
    held_during_call = []

    def track(ctx: NodeContext[_Memory, _Output], value: _Input) -> _Output:
        held_during_call.append(node_runtime.firing_lock.locked())
        return _Output(value.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()
    node_runtime = run.node_runtime(track)

    assert not node_runtime.firing_lock.locked()

    run.publish(_Input(1))

    assert held_during_call == [True]
    assert not node_runtime.firing_lock.locked()


def test_two_firings_of_the_same_stateful_node_runtime_cannot_overlap_under_real_concurrency():
    active = 0
    max_active = 0
    lock = threading.Lock()

    def track(ctx: NodeContext[_Memory, _Output], value: _Input) -> _Output:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return _Output(value.value)

    flow = Flow()
    flow.add(track, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    threads = [
        threading.Thread(target=run.publish, args=(_Input(value),))
        for value in (1, 2, 3)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert max_active == 1
