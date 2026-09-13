"""
Milestone O2, Slices O2a-O2d -- Instrument declaration and ctx.record().

Covers docs/observability_goals.md Section 2 and docs/observability_non_goals.md
Section 2/3:

    1. `Instrument` validates its `kind` against gauge/counter/updown_counter.
    2. `flow.add(node, instruments=[...])` attaches declared Instruments to
       a FlowNode.
    3. Declared mode: ctx.record(instrument, value) and ctx.record(name, value)
       both work for a declared name; an undeclared name raises.
    4. Lazy mode: ctx.record(name, value, unit=...) with no instruments=[...]
       works; the first observed unit is authoritative, a later mismatched
       unit raises.
    5. Recording.value must be scalar.
    6. A NodeContext without a recorder (not built by a real firing) raises
       on ctx.record(...).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def test_instrument_rejects_invalid_kind():
    from reed.observability.instrument import Instrument

    with pytest.raises(ValueError):
        Instrument(name="speed", kind="histogram", unit="m/s")  # type: ignore[arg-type]


def test_instrument_accepts_valid_kinds():
    from reed.observability.instrument import Instrument

    for kind in ("gauge", "counter", "updown_counter"):
        instrument = Instrument(name="x", kind=kind, unit="u")  # type: ignore[arg-type]
        assert instrument.kind == kind


def test_flow_add_attaches_declared_instruments():
    from reed import Flow
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow_node = flow.add(produce, instruments=[speed])

    assert flow_node.instruments == (speed,)


def test_declared_mode_accepts_instrument_object_and_matching_name():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(speed, measurement.value)
        ctx.record("speed", measurement.value + 1)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[speed])
    run = flow.run()

    run.publish(Measurement(10))

    recordings = run.node_runtime(track).recordings
    assert len(recordings) == 2
    assert all(r.name == "speed" for r in recordings)
    assert all(r.kind == "gauge" for r in recordings)
    assert all(r.unit == "m/s" for r in recordings)
    assert [r.value for r in recordings] == [10, 11]


def test_declared_mode_rejects_undeclared_name():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record("not_declared", measurement.value)
        return Estimate(measurement.value)

    from reed.observability.instrument import Instrument

    flow = Flow()
    flow.add(track, instruments=[Instrument(name="speed", kind="gauge", unit="m/s")])
    run = flow.run()

    with pytest.raises(ValueError):
        run.publish(Measurement(1))


def test_lazy_mode_accepts_plain_name_with_no_declaration():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record("reason", "conflict avoidance")
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    run.publish(Measurement(1))

    recordings = run.node_runtime(track).recordings
    assert len(recordings) == 1
    assert recordings[0].name == "reason"
    assert recordings[0].kind is None
    assert recordings[0].value == "conflict avoidance"


def test_lazy_mode_first_observed_unit_is_authoritative():
    from reed import Flow, NodeContext

    calls = {"n": 0}

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        calls["n"] += 1
        if calls["n"] == 1:
            ctx.record("speed", measurement.value, unit="m/s")
        else:
            ctx.record("speed", measurement.value, unit="mph")
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    run.publish(Measurement(1))

    with pytest.raises(ValueError):
        run.publish(Measurement(2))


def test_recording_value_must_be_scalar():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record("bad", [1, 2, 3])  # type: ignore[arg-type]
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    with pytest.raises(TypeError):
        run.publish(Measurement(1))


def test_ctx_record_without_recorder_raises():
    from reed import NodeContext

    ctx = NodeContext(memory=None, last_output=None)

    with pytest.raises(RuntimeError):
        ctx.record("x", 1)


def test_lazy_mode_recording_kind_is_always_none_slice_o2e():
    """Milestone O2, Slice O2e (docs/observability_design.md Section 19): a
    non-metric fact recorded with no Instrument always has kind=None."""
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record("plain_fact", 42)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()
    run.publish(Measurement(1))

    recordings = run.node_runtime(track).recordings
    assert recordings[0].kind is None


def test_declared_mode_recording_kind_is_never_none_slice_o2e():
    """Milestone O2, Slice O2e: declared mode (an Instrument backs the
    Recording) always has a concrete kind -- declaring an Instrument is
    never the path for a non-metric fact."""
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    counter = Instrument(name="events_seen", kind="counter", unit="1")

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(counter, 1)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[counter])
    run = flow.run()
    run.publish(Measurement(1))

    recordings = run.node_runtime(track).recordings
    assert recordings[0].kind == "counter"
