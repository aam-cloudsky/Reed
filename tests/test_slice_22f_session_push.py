"""
Focused tests for Slice 22F -- `Session.push(self) -> None`
(docs/refactor/session_snapshot_decision.md section 5 "`push()` and
`snapshot()`"; docs/refactor/architectural_invariants.md #18, #19, #31,
#32).

These tests exercise `push()`'s SliceContract-required behaviors
directly through the public `Flow`/`Session` surface:

    - it fires a `FlowNode` made eligible by a prior `feed()`
      (`feed()` itself never fires anything, invariant #31 -- only
      `push()` does);
    - it cascades a firing's committed output downstream to quiescence,
      exactly as `publish()`'s cascade does, multiple hops deep;
    - it returns `None`, strictly (invariant #32);
    - a second `push()` call with no intervening `feed()` is a genuine
      no-op -- quiescent immediately, nothing fires;
    - it respects issue #21's SAMPLED-vs-TRIGGERING eligibility split:
      feeding a SAMPLED-role value alone never makes its consuming node
      eligible, but feeding a TRIGGERING-role value does (using the
      node's other, already-fed SAMPLED value).
"""

from __future__ import annotations

from typing import Annotated

from reed import Flow, NodeContext, TriggerPolicy
from reed.composition.node.sampled import Sampled


class RawReading:
    def __init__(self, value: float) -> None:
        self.value = value


class CalibrationOffset:
    def __init__(self, value: float) -> None:
        self.value = value


class CalibratedReading:
    def __init__(self, value: float) -> None:
        self.value = value


class DisplayedReading:
    def __init__(self, value: float) -> None:
        self.value = value


class _Memory:
    pass


def test_push_fires_nodes_made_eligible_by_a_prior_feed():
    fired: list[float] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        fired.append(reading.value)
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(RawReading(1.0))
    assert fired == []  # feed() alone never fires anything (invariant #31)

    session.push()

    assert fired == [1.0]
    assert session.repository.get_artifact_record(CalibratedReading).value.value == 1.0


def test_push_cascades_downstream_to_quiescence():
    fired: list[str] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        fired.append("calibrate")
        return CalibratedReading(reading.value * 2)

    def display(reading: CalibratedReading) -> DisplayedReading:
        fired.append("display")
        return DisplayedReading(reading.value + 1)

    flow = Flow()
    flow.add(calibrate)
    flow.add(display)
    session = flow.session()

    session.feed(RawReading(5.0))
    session.push()

    assert fired == ["calibrate", "display"]
    assert session.repository.get_artifact_record(CalibratedReading).value.value == 10.0
    assert session.repository.get_artifact_record(DisplayedReading).value.value == 11.0


def test_push_returns_none():
    def calibrate(reading: RawReading) -> CalibratedReading:
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(RawReading(1.0))
    result = session.push()

    assert result is None

    # Also None when there is nothing to do at all -- no feed(), no
    # nodes, quiescent from the start.
    assert Flow().session().push() is None


def test_second_push_with_no_intervening_feed_fires_nothing():
    fired: list[float] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        fired.append(reading.value)
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(RawReading(1.0))
    session.push()
    assert fired == [1.0]

    session.push()  # no intervening feed() -- must fire nothing

    assert fired == [1.0]
    assert session.repository.get_artifact_record(CalibratedReading).value.value == 1.0


def test_second_push_with_no_intervening_feed_fires_nothing_any_input_changed():
    # Same no-op guarantee, but for TriggerPolicy.ANY_INPUT_CHANGED --
    # `_fire()` itself only clears `_fresh_since_last_firing` for
    # ALL_INPUTS_CHANGED, so push() must do its own clearing for this
    # policy too, or the node's freshness would never be spent and a
    # second push() would wrongly refire it.
    fired: list[float] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        fired.append(reading.value)
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(RawReading(1.0))
    session.push()
    assert fired == [1.0]

    session.push()

    assert fired == [1.0]


def test_push_respects_sampled_vs_triggering_eligibility_from_issue_21():
    fired: list[str] = []

    def calibrate(
        reading: RawReading, offset: Annotated[CalibrationOffset, Sampled]
    ) -> CalibratedReading:
        fired.append("calibrate")
        return CalibratedReading(reading.value + offset.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    # A SAMPLED-role feed alone must never make the node eligible, even
    # though it may complete coverage.
    session.feed(CalibrationOffset(0.5))
    session.push()
    assert fired == []

    # A TRIGGERING-role feed does make it eligible, using the latest
    # last-known SAMPLED value.
    session.feed(RawReading(10.0))
    session.push()

    assert fired == ["calibrate"]
    assert session.repository.get_artifact_record(CalibratedReading).value.value == 10.5

