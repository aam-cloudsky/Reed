# pyright: strict
"""
Propagation plan for one `Session.push()` call (GitHub issue #31).

`PropagationPlan` decides *which* `FlowNode`s may run in the next superstep.
It holds no artifact values and performs no firing; `Session.push()` asks it
for the next ready set, runs those nodes' workers, commits their outputs at
the barrier, and reports back which nodes are settled.

Vocabulary:

- **Affected**: a node that may still fire in this `push()`. The seed nodes
  (those with pending freshness) are affected, and so is every node that
  consumes a type produced by an affected node.
- **Settled**: an affected node that either fired or was found not eligible
  at its turn. A settled node never fires again in the same `push()`
  (rule 1: at most one firing per node and instance per `push()`).
- **Ready**: an affected, unsettled node whose affected producers are all
  settled (rule 2: a node runs only after every producer of its inputs that
  may still fire in this `push()`).

When affected nodes remain but none is ready, some of them wait on each
other: a feedback loop. Only a loop that waits on nothing outside itself can
be released (a sink strongly connected component of the wait-for graph;
Tarjan, SIAM J. Comput. 1(2), 1972, doi:10.1137/0201010). Inside it, the
plan prefers a node that waits on the loop only through *delay* edges
(`Sampled` inputs), then the node reached first by the change front, then
registration order (rule 3). The inputs the released node reads along the
loop are the values committed before this `push()`, which makes the return
path an implicit unit delay, the semantics of Lustre's `pre` (Halbwachs et
al., Proc. IEEE 79(9), 1991, doi:10.1109/5.97300).

Each call to `next_superstep()` corresponds to one superstep of the Bulk
Synchronous Parallel model (Valiant, CACM 33(8), 1990,
doi:10.1145/79173.79181): the nodes it returns read the same committed state,
and their outputs become visible only at the barrier that follows.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Iterator, Sequence
from typing import Generic, TypeVar

NodeT = TypeVar("NodeT", bound=Hashable)


class PropagationPlan(Generic[NodeT]):
    """Per-`push()` bookkeeping of affected, settled and ready nodes."""

    def __init__(
        self,
        nodes_in_registration_order: Sequence[NodeT],
        seeds: Iterable[NodeT],
        *,
        downstream_of: Callable[[NodeT], Sequence[NodeT]],
        upstream_of: Callable[[NodeT], Sequence[NodeT]],
        delay_upstream_of: Callable[[NodeT], Sequence[NodeT]] | None = None,
    ) -> None:
        """
        `upstream_of(node)` lists the producers of `node`'s inputs.
        `delay_upstream_of(node)` lists the subset connected to `node` only
        through delay edges (`Sampled` inputs); a loop is preferably broken
        there. Without it, no edge is treated as a delay.
        """
        self._registration_index: dict[NodeT, int] = {
            node: index for index, node in enumerate(nodes_in_registration_order)
        }
        self._upstream_of = upstream_of
        self._delay_upstream_of: Callable[[NodeT], Sequence[NodeT]] = (
            delay_upstream_of if delay_upstream_of is not None else _no_delay_edges
        )
        self._reached_at: dict[NodeT, int] = {}
        self._settled: set[NodeT] = set()
        self._reach(seeds, downstream_of)

    def _reach(
        self, seeds: Iterable[NodeT], downstream_of: Callable[[NodeT], Sequence[NodeT]]
    ) -> None:
        """Breadth-first closure from the seeds, recording the change front."""
        frontier = sorted(set(seeds), key=self._order_key)
        for node in frontier:
            self._reached_at[node] = 0
        distance = 0
        while frontier:
            distance += 1
            following: list[NodeT] = []
            for node in frontier:
                for consumer in downstream_of(node):
                    if consumer not in self._reached_at:
                        self._reached_at[consumer] = distance
                        following.append(consumer)
            frontier = sorted(following, key=self._order_key)

    def _order_key(self, node: NodeT) -> int:
        return self._registration_index[node]

    @property
    def pending(self) -> tuple[NodeT, ...]:
        """Affected nodes not yet settled, in registration order."""
        return tuple(
            sorted(
                (node for node in self._reached_at if node not in self._settled),
                key=self._order_key,
            )
        )

    def next_superstep(self) -> tuple[NodeT, ...]:
        """
        The nodes that run in the next superstep, in registration order.

        Empty only when every affected node is settled (quiescence). When no
        node is ready, exactly one node of a releasable loop is returned
        (see the module docstring).
        """
        pending = self.pending
        if not pending:
            return ()
        ready = tuple(node for node in pending if not self._waits_on(node))
        if ready:
            return ready
        return (self._release(pending),)

    def _waits_on(self, node: NodeT) -> tuple[NodeT, ...]:
        """Producers of `node` that are affected and not yet settled."""
        return tuple(
            producer
            for producer in self._upstream_of(node)
            if producer in self._reached_at and producer not in self._settled
        )

    def _release(self, pending: tuple[NodeT, ...]) -> NodeT:
        candidates = [
            node
            for component in _strongly_connected(pending, self._waits_on)
            if _is_sink(component, self._waits_on)
            for node in component
        ]

        def preference(node: NodeT) -> tuple[bool, int, int]:
            in_loop = [p for p in self._waits_on(node) if p in candidates]
            delays = set(self._delay_upstream_of(node))
            through_delay_only = all(p in delays for p in in_loop)
            return (not through_delay_only, self._reached_at[node], self._order_key(node))

        return min(candidates, key=preference)

    def settle(self, nodes: Iterable[NodeT]) -> None:
        """Mark nodes as fired or discarded for the rest of this `push()`."""
        self._settled.update(nodes)


def _no_delay_edges(node: object) -> tuple[()]:
    return ()


def _strongly_connected(
    nodes: Sequence[NodeT], successors: Callable[[NodeT], Sequence[NodeT]]
) -> list[list[NodeT]]:
    """Tarjan's algorithm over `nodes`, iterative, deterministic in input order."""
    index: dict[NodeT, int] = {}
    low: dict[NodeT, int] = {}
    on_stack: set[NodeT] = set()
    stack: list[NodeT] = []
    components: list[list[NodeT]] = []
    universe = set(nodes)
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work: list[tuple[NodeT, Iterator[NodeT]]] = []
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work.append((root, iter([n for n in successors(root) if n in universe])))
        while work:
            node, children = work[-1]
            child = next(children, None)
            if child is not None:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter([n for n in successors(child) if n in universe])))
                elif child in on_stack:
                    low[node] = min(low[node], index[child])
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component: list[NodeT] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
    return components


def _is_sink(component: list[NodeT], successors: Callable[[NodeT], Sequence[NodeT]]) -> bool:
    """True when no member waits on a node outside the component."""
    members = set(component)
    return all(target in members for node in component for target in successors(node))
