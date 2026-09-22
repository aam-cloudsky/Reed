"""
Demonstrate sampled inputs and the Session execution API.

A sampled input participates in node execution but does not trigger execution
when it changes. Here, CalibrationOffset is sampled by calibrate,
while RawReading is the triggering input.

The example also demonstrates the two equivalent Session APIs:

session.feed(value)
session.push()
snapshot = session.snapshot()

and the convenience form:

snapshot = session.invoke(value)

Snapshots preserve the artifact state captured at that point and are not
affected by subsequent Session updates.

Note:
Artifact types are defined as runtime-distinct subclasses rather than with
NewType. NewType provides a distinct type to static type checkers,
but its values retain the underlying runtime type. Reed identifies
artifacts by their runtime types.
"""

from typing import Annotated

from reed import Flow, Sampled, TriggerPolicy


# ============================================================================
# Domain types
# ============================================================================

class CalibrationOffset(float):
    pass


class CalibratedReading(float):
    pass


class RawReading(float):
    pass


# ============================================================================
# Nodes
# ============================================================================


def calibrate(
    raw: RawReading,
    offset: Annotated[CalibrationOffset, Sampled],
) -> CalibratedReading:
    return CalibratedReading(raw * offset)


# ============================================================================
# Flow composition
# ============================================================================

flow = Flow()

flow.add(
    calibrate,
    trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED,
)


# ============================================================================
# Execution
# ============================================================================


if __name__ == "__main__":

    session = flow.session()
    session.feed(CalibrationOffset(0.5))
    session.push()

    print()
    print("=" * 72)
    print("Explicit feed → push → snapshot lifecycle")
    print("=" * 72)

    raw = 10
    session.feed(RawReading(raw))
    session.push()
    snap1 = session.snapshot()

    reading_calibrated = snap1.get(CalibratedReading)
    if reading_calibrated:
        print("Raw Reading:", raw, "Reading Calibrated:", reading_calibrated)

    print()
    print("=" * 72)
    print("Convenience API: invoke() performs feed → push → snapshot")
    print("=" * 72)

    raw = 20
    snap2 = session.invoke(RawReading(raw))
    reading_calibrated = snap2.get(CalibratedReading)
    if reading_calibrated:
        print("Raw Reading:", raw, "Reading Calibrated:", reading_calibrated)

    assert snap1[CalibratedReading] == 5.0
    assert snap2[CalibratedReading] == 10.0
