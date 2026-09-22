"""
Milestone O5, Slice O5a -- Level 1 Execution Trace (in-memory ring buffer).

Covers docs/observability_design.md Section 11.1:

    1. Every firing records a "node_started" then a "node_finished"
       TraceEvent, unconditionally (no storage_root opt-in, unlike
       Recordings/Provenance).
    2. TraceEvents carry the same identity fields as Recordings/Provenance
       (execution_id, flow_id, node_id, node_execution_id, execution_seq).
    3. ExecutionTrace is a bounded ring buffer: appending past capacity
       drops the oldest entries.
"""

from __future__ import annotations

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def test_firing_records_started_then_finished_events():
    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    events = session.trace.events
    # feed()'s own commit of the externally supplied Measurement also
    # records a "node_finished" TraceEvent (Slice 22E), but never a
    # "node_started" one -- feed() is not a real function call with a
    # start/end duration. Only push()'s firing of produce gets the
    # started+finished pair.
    assert len(events) == 3
    produce_events = [e for e in events if e.node_id.endswith("produce")]
    assert len(produce_events) == 2
    assert produce_events[0].event_type == "node_started"
    assert produce_events[1].event_type == "node_finished"
    assert produce_events[0].node_execution_id == produce_events[1].node_execution_id
    assert produce_events[0].execution_seq == produce_events[1].execution_seq


def test_trace_events_carry_identity_fields():
    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    for event in session.trace.events:
        assert event.execution_id == session.execution_id
        assert event.flow_id == session.flow_id

    # feed()'s own "node_finished" event for Measurement comes first
    # (execution_seq 1, node_id the fed type's own identity); produce's
    # own started/finished pair follows with execution_seq 2 (Slice
    # 22E: feed() mints a real NodeExecutionIdentity too).
    produce_event = next(
        e for e in session.trace.events if e.node_id.endswith("produce")
    )
    assert produce_event.execution_seq == 2


def test_trace_is_populated_with_no_storage_root_configured():
    """Level 1 has no opt-in -- unlike recording_store/provenance_store,
    trace is always populated regardless of storage_root."""
    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    assert session.recording_store is None
    assert session.provenance_store is None
    # feed()'s own "node_finished" event plus produce's
    # "node_started"/"node_finished" pair (Slice 22E).
    assert len(session.trace) == 3


def test_ring_buffer_drops_oldest_past_capacity():
    from reed.observability.trace import ExecutionTrace, TraceEvent

    trace = ExecutionTrace(capacity=2)
    for i in range(3):
        trace.record(
            TraceEvent(
                event_type="node_started",
                execution_id="exec",
                flow_id="flow",
                node_id="node",
                node_execution_id=f"ne-{i}",
                execution_seq=i,
                timestamp=0.0,
            )
        )

    events = trace.events
    assert len(events) == 2
    assert [e.node_execution_id for e in events] == ["ne-1", "ne-2"]


def test_execution_trace_rejects_non_positive_capacity():
    from reed.observability.trace import ExecutionTrace

    with pytest.raises(ValueError):
        ExecutionTrace(capacity=0)
