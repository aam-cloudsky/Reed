"""
Self-flow with many instances: consensus.

Each agent moves to the average of every agent's position. `consensus` reads
`Collective[Position]` marked `Sampled`, so every agent sees the positions
committed before the step, never ones already updated in the same push().
All three start at 0, 30 and 60 and agree on 30 after one step.
"""

from dataclasses import dataclass
from typing import Annotated

from reed import Collective, Flow, InstanceKey, Sampled


@dataclass(frozen=True)
class Step:
    k: int


@dataclass(frozen=True)
class Position:
    x: float


def consensus(
    step: Step, everyone: Annotated[Collective[Position], Sampled]
) -> Position:
    return Position(sum(p.x for p in everyone) / len(everyone))


flow = Flow()
flow.add(consensus)


if __name__ == "__main__":
    agents = [InstanceKey(key=name) for name in ("a", "b", "c")]

    session = flow.session(observability="silent")
    session.feed_instances(
        dict(zip(agents, (Position(0.0), Position(30.0), Position(60.0))))
    )
    session.feed_instances({agent: Step(1) for agent in agents})
    session.push()

    positions = session.snapshot().instances(Position)
    for agent in agents:
        print(agent.key, positions[agent].x)

    assert [positions[agent] for agent in agents] == [Position(30.0)] * 3
