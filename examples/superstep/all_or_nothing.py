"""
All or nothing: a failing worker commits nothing from its superstep.

`calibrate` runs once per sensor. One sensor sends a negative reading and its
worker raises. None of the three calibrated values is committed. After the
fault is fixed, the next push() retries the same pending work.
"""

from dataclasses import dataclass

from reed import Flow, InstanceKey


@dataclass(frozen=True)
class Reading:
    value: float


@dataclass(frozen=True)
class Calibrated:
    value: float


faulty = True


def calibrate(reading: Reading) -> Calibrated:
    if faulty and reading.value < 0:
        raise ValueError("negative reading")
    return Calibrated(abs(reading.value))


flow = Flow()
flow.add(calibrate)


if __name__ == "__main__":
    session = flow.session(observability="silent")
    session.feed_instances(
        {
            InstanceKey(key="north"): Reading(1.0),
            InstanceKey(key="south"): Reading(-2.0),
            InstanceKey(key="east"): Reading(3.0),
        }
    )

    try:
        session.push()
    except ValueError as error:
        print("push() failed:", error)
    committed = session.repository.get_all_artifact_records(Calibrated)
    print("committed after the failure:", len(committed))
    assert len(committed) == 0

    faulty = False
    session.push()
    committed = session.repository.get_all_artifact_records(Calibrated)
    print("committed after the retry:", len(committed))
    assert len(committed) == 3
