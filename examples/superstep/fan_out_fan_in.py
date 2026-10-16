"""
Fan-out / fan-in with a superstep barrier.

`calibrate` consumes one sensor reading, so it runs once per sensor instance
(fan-out). `average` consumes `Collective[Calibrated]`, so it runs
only after every `calibrate` worker has finished, and receives all of their
outputs at once (fan-in). The workers' outputs are committed together, at the
barrier that closes their superstep: `average` never sees a partial set.
"""

from dataclasses import dataclass
from reed import Collective, Flow, InstanceKey


@dataclass(frozen=True)
class Reading:
    value: float


@dataclass(frozen=True)
class Calibrated:
    value: float


@dataclass(frozen=True)
class Average:
    value: float


def calibrate(reading: Reading) -> Calibrated:
    return Calibrated(reading.value * 2)


def average(calibrated: Collective[Calibrated]) -> Average:
    values = [c.value for c in calibrated]
    print("average received:", values)
    return Average(sum(values) / len(values))


flow = Flow()
flow.add(calibrate)
flow.add(average)


if __name__ == "__main__":
    session = flow.session(observability="silent")
    session.feed_instances(
        {
            InstanceKey(key="north"): Reading(1.0),
            InstanceKey(key="south"): Reading(2.0),
            InstanceKey(key="east"): Reading(3.0),
        }
    )
    session.push()

    print("average:", session.snapshot()[Average])
    assert session.snapshot()[Average] == Average(4.0)
