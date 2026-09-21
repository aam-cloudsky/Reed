"""
Do not use NewType(), it is an alias and not an real type.
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

    run = flow.run()

    print("=" * 72)
    print("Publishing a CalibrationOffset before any RawReading exists")
    print("(SAMPLED-only: not yet covered, cannot fire)")
    print("=" * 72)

    run.publish(CalibrationOffset(0.5))

    print()
    print("=" * 72)
    print("Publishing the first RawReading")
    print("(now covered; the arrival is TRIGGERING, so it fires)")
    print("=" * 72)

    print("Raw Reading:", 10)
    run.publish(RawReading(10.0))

    reading_calibrated = run.repository.get(CalibratedReading)
    if reading_calibrated:
        print("Reading Calibrated:", reading_calibrated)

    print("Raw Reading:", 10)
    run.publish(RawReading(20.0))
    reading = run.repository.get(CalibratedReading)
    if reading_calibrated:
        print("Reading Calibrated:", reading_calibrated)
