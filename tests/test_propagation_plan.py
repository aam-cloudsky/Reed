"""
Unit tests for `reed.execution.propagation.PropagationPlan` (issue #31).

The plan is pure bookkeeping over an abstract graph, so it is tested here
with plain strings as nodes, independently of `Session`.
"""

from __future__ import annotations

from collections.abc import Sequence

from reed.execution.propagation import PropagationPlan


def make_plan(
    order: Sequence[str],
    edges: dict[str, list[str]],
    seeds: list[str],
) -> PropagationPlan[str]:
    """`edges` maps a producer to its consumers."""
    upstream: dict[str, list[str]] = {node: [] for node in order}
    for producer, consumers in edges.items():
        for consumer in consumers:
            upstream[consumer].append(producer)
    return PropagationPlan(
        order,
        seeds,
        downstream_of=lambda node: edges.get(node, []),
        upstream_of=lambda node: upstream[node],
    )


def run(plan: PropagationPlan[str]) -> list[tuple[str, ...]]:
    supersteps: list[tuple[str, ...]] = []
    while True:
        step = plan.next_superstep()
        if not step:
            return supersteps
        supersteps.append(step)
        plan.settle(step)


def test_diamond_runs_join_after_both_branches() -> None:
    plan = make_plan(
        ["left", "right", "join"],
        {"left": ["join"], "right": ["join"]},
        seeds=["left", "right"],
    )
    assert run(plan) == [("left", "right"), ("join",)]


def test_chain_runs_one_node_per_superstep() -> None:
    plan = make_plan(["a", "b", "c"], {"a": ["b"], "b": ["c"]}, seeds=["a"])
    assert run(plan) == [("a",), ("b",), ("c",)]


def test_unaffected_producer_does_not_block_its_consumer() -> None:
    # "other" produces an input of "join" but has no pending change.
    plan = make_plan(
        ["source", "other", "join"],
        {"source": ["join"], "other": ["join"]},
        seeds=["source"],
    )
    assert run(plan) == [("source",), ("join",)]


def test_feedback_loop_releases_the_node_reached_first() -> None:
    # n1 -> n2 -> n1; the change enters at n1.
    plan = make_plan(["n1", "n2"], {"n1": ["n2"], "n2": ["n1"]}, seeds=["n1"])
    assert run(plan) == [("n1",), ("n2",)]


def test_feedback_loop_entry_point_decides_the_release() -> None:
    plan = make_plan(["n1", "n2"], {"n1": ["n2"], "n2": ["n1"]}, seeds=["n2"])
    assert run(plan) == [("n2",), ("n1",)]


def test_registration_order_breaks_ties_between_equally_reached_nodes() -> None:
    plan = make_plan(["b", "a"], {"a": ["b"], "b": ["a"]}, seeds=["a", "b"])
    assert run(plan) == [("b",), ("a",)]


def test_every_affected_node_runs_at_most_once() -> None:
    edges = {"s": ["x", "y"], "x": ["z"], "y": ["z"], "z": ["x"]}
    plan = make_plan(["s", "x", "y", "z"], edges, seeds=["s"])
    supersteps = run(plan)
    flattened = [node for step in supersteps for node in step]
    assert sorted(flattened) == ["s", "x", "y", "z"]
    assert len(flattened) == len(set(flattened))


def test_no_seeds_means_quiescence() -> None:
    plan = make_plan(["a"], {}, seeds=[])
    assert plan.next_superstep() == ()


def test_loop_release_follows_the_change_front_not_registration_order() -> None:
    # s -> x -> y -> x. y is registered before x, but the change front
    # reaches x first (distance 1) and y second (distance 2).
    plan = make_plan(
        ["y", "x", "s"],
        {"s": ["x"], "x": ["y"], "y": ["x"]},
        seeds=["s"],
    )
    assert run(plan) == [("s",), ("x",), ("y",)]


def test_a_node_waiting_on_a_loop_is_not_released_before_the_loop() -> None:
    # r depends on p; p <-> q is a loop; s feeds p. r is a seed and is
    # registered first, but it is not in the loop: the loop must be
    # released first and r must run after p.
    plan = make_plan(
        ["r", "s", "p", "q"],
        {"s": ["p"], "p": ["q", "r"], "q": ["p"]},
        seeds=["s", "r"],
    )
    supersteps = run(plan)
    flattened = [node for step in supersteps for node in step]
    assert flattened.index("r") > flattened.index("p")


def test_loop_is_broken_at_a_delay_edge_first() -> None:
    # agg <- worker (collective edge), worker <- agg (sampled, delay edge).
    # Both are seeds; agg is registered first. The loop is broken where the
    # delay is, so worker runs first and agg sees its fresh output.
    order = ["agg", "worker"]
    edges = {"worker": ["agg"], "agg": ["worker"]}
    upstream = {"agg": ["worker"], "worker": ["agg"]}
    plan: PropagationPlan[str] = PropagationPlan(
        order,
        ["agg", "worker"],
        downstream_of=lambda node: edges[node],
        upstream_of=lambda node: upstream[node],
        delay_upstream_of=lambda node: ["agg"] if node == "worker" else [],
    )
    assert run(plan) == [("worker",), ("agg",)]
