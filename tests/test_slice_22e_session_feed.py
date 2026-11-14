"""
Focused tests for Slice 22E -- `Session.feed(value)`
(docs/refactor/session_snapshot_decision.md section 4 "`feed()` is a
node"; docs/refactor/architectural_invariants.md #10, #29, #30, #31).

These tests exercise `feed()`'s six SliceContract-required behaviors
directly through the public `Flow`/`Session` surface:

    - it commits a real, versioned `ArtifactRecord` tagged
      `origin=ArtifactOrigin.EXTERNAL`;
    - it never fires any node itself (that's `push()`'s job, Slice 22F,
      not yet implemented);
    - it marks TRIGGERING-role consumers fresh but leaves SAMPLED-role
      consumers unmarked (issue #21's existing `_record_input`
      distinction, reused unchanged);
    - it is exempt from `DuplicateArtifactProducerError` -- it may
      overwrite a type that already has a declared producer node;
    - it fires the same observability hooks a node firing does
      (generated-provenance event, trace event, `on_output` dispatch)
      via the shared commit path;
    - the resulting record's `dependencies` is always `{}`.
"""

from __future__ import annotations

from typing import Annotated

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


def test_feed_commits_a_versioned_record_with_origin_external():
    from reed import Flow
    from reed.execution.artifact_record import ArtifactOrigin, ArtifactVersion

    flow = Flow()
    session = flow.session()

    session.feed(RawReading(1.0))
    session.push()  # feed only stages the value; push() applies it (#34)

    record = session.repository.get_artifact_record(RawReading)
    assert record is not None
    assert record.value.value == 1.0
    assert record.provenance.origin is ArtifactOrigin.EXTERNAL
    assert record.provenance.producer is None
    assert record.version == ArtifactVersion.initial()

    session.feed(RawReading(2.0))
    session.push()  # feed only stages the value; push() applies it (#34)
    second = session.repository.get_artifact_record(RawReading)
    assert second is record
    assert record.version.number == 2
    assert record.value.value == 2.0


def test_feed_does_not_fire_any_node():
    from reed import Flow

    calls: list[RawReading] = []

    def calibrate(reading: RawReading) -> CalibratedReading:
        calls.append(reading)
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(RawReading(3.0))

    assert calls == []
    assert session.repository.get_artifact_record(CalibratedReading) is None


def test_feed_marks_triggering_consumers_fresh_but_not_sampled_consumers():
    from reed import Flow

    def calibrate(
        reading: RawReading, offset: Annotated[CalibrationOffset, Sampled]
    ) -> CalibratedReading:
        return CalibratedReading(reading.value + offset.value)

    flow = Flow()
    flow_node = flow.add(calibrate)
    session = flow.session()

    from reed.execution.instance_key import InstanceKey

    session.feed(CalibrationOffset(0.5))
    # Applies the staged feed without propagating it, as push() does first (#34).
    session._apply_pending()
    fresh = session._fresh_since_last_firing.get(flow_node, {}).get(
        InstanceKey.singleton(), set()
    )
    assert CalibrationOffset not in fresh
    assert (
        session._last_known_values[flow_node][InstanceKey.singleton()][
            CalibrationOffset
        ].value
        == 0.5
    )

    session.feed(RawReading(10.0))
    # Applies the staged feed without propagating it, as push() does first (#34).
    session._apply_pending()
    fresh = session._fresh_since_last_firing.get(flow_node, {}).get(
        InstanceKey.singleton(), set()
    )
    assert RawReading in fresh
    assert CalibrationOffset not in fresh


def test_feed_may_overwrite_a_type_that_already_has_a_declared_producer():
    from reed import Flow

    def calibrate(reading: RawReading) -> CalibratedReading:
        return CalibratedReading(reading.value)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    session.feed(CalibratedReading(99.0))
    session.push()  # feed only stages the value; push() applies it (#34)

    record = session.repository.get_artifact_record(CalibratedReading)
    assert record is not None
    assert record.value.value == 99.0


def test_feed_fires_generated_provenance_and_trace_events_and_dispatches_on_output():
    from reed import Flow
    from reed.observability.trace import TraceEvent

    def calibrate(reading: RawReading) -> CalibratedReading:
        return CalibratedReading(reading.value)

    observed: list[CalibratedReading] = []

    def on_output(value: CalibratedReading) -> None:
        observed.append(value)

    flow = Flow()
    flow.add(calibrate, on_output=on_output)
    session = flow.session()

    seq_before = session._execution_seq_counter
    trace_before = len(session.trace.events)

    session.feed(CalibratedReading(42.0))
    session.push()  # feed only stages the value; push() applies it (#34)

    assert session._execution_seq_counter == seq_before + 1

    new_trace_events = list(session.trace.events)[trace_before:]
    assert len(new_trace_events) == 1
    trace_event = new_trace_events[0]
    assert isinstance(trace_event, TraceEvent)
    assert trace_event.event_type == "node_finished"

    assert len(observed) == 1
    assert observed[0].value == 42.0
    assert session.callback_failures == []


def test_fed_record_has_empty_dependencies():
    from reed import Flow

    flow = Flow()
    session = flow.session()

    session.feed(RawReading(5.0))
    session.push()  # feed only stages the value; push() applies it (#34)

    record = session.repository.get_artifact_record(RawReading)
    assert record.provenance.dependencies == {}
