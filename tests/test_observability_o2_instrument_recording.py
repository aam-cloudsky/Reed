"""
Milestone O2, Slices O2a-O2d -- Instrument declaration and ctx.record();
redesigned at Milestone O7, Slice O7i for typed Instrument Definitions
discovered dynamically (`reed.observability.instrument`'s module docstring).

Covers docs/observability_goals.md Section 2 and docs/observability_non_goals.md
Section 2/3, as amended by the O7i redesign:

    1. `Instrument` subclasses validate `kind`/`unit` at class-definition
       time (`__init_subclass__`) and at `ctx.record(...)` time.
    2. `ctx.record(SomeInstrument, value)` -- the Instrument subclass
       itself, never an instance and never a plain string -- is the only
       recording path; there is no more `flow.add(node, instruments=[...])`
       and no more lazy-mode plain-string recording.
    3. Instruments are discovered dynamically: no declaration step is
       needed before a Node's first `ctx.record(...)` call.
    4. Recording.value must be scalar.
    5. A NodeContext without a recorder (not built by a real firing) raises
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


def test_instrument_subclass_rejects_invalid_kind():
    from reed.observability.instrument import Instrument

    with pytest.raises(TypeError):

        class Speed(Instrument[float]):
            kind = "histogram"  # type: ignore[assignment]
            unit = "m/s"


def test_instrument_subclass_rejects_invalid_unit():
    from reed.observability.instrument import Instrument, InstrumentKind

    with pytest.raises(TypeError):

        class Speed(Instrument[float]):
            kind = InstrumentKind.GAUGE
            unit = 123  # type: ignore[assignment]


def test_instrument_accepts_valid_kinds():
    from reed.observability.instrument import Instrument, InstrumentKind

    for kind in InstrumentKind:

        class Metric(Instrument[float]):
            pass

        Metric.kind = kind
        Metric.unit = "u"
        assert Metric.kind == kind


def test_flow_add_no_longer_accepts_instruments_parameter():
    """O7i: Instrument discovery replaced prospective declaration --
    `flow.add(...)` no longer has an `instruments=` parameter at all."""
    from reed import Flow

    def produce() -> Measurement:
        return Measurement(1)

    flow = Flow()
    with pytest.raises(TypeError):
        flow.add(produce, instruments=[])  # type: ignore[call-arg]


def test_ctx_record_with_typed_instrument_discovers_it_dynamically():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(Speed, float(measurement.value))
        ctx.record(Speed, float(measurement.value) + 1)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed(Measurement(10))
    session.push()

    recordings = session.node_session(track).recordings
    assert len(recordings) == 2
    assert all(r.name == Speed.instrument_name() for r in recordings)
    assert all(r.kind == "gauge" for r in recordings)
    assert all(r.unit == "m/s" for r in recordings)
    assert [r.value for r in recordings] == [10.0, 11.0]


def test_ctx_record_rejects_a_plain_string_name():
    """O7i removed the old lazy-mode plain-string path entirely --
    ctx.record(...) now requires an Instrument subclass."""
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record("reason", "conflict avoidance")  # type: ignore[arg-type]
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    with pytest.raises(TypeError):
        session.feed(Measurement(1))
        session.push()


def test_ctx_record_rejects_an_instrument_instance_not_the_class():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(Speed(), float(measurement.value))  # type: ignore[arg-type]
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    with pytest.raises(TypeError):
        session.feed(Measurement(1))
        session.push()


def test_recording_value_must_be_scalar():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Bad(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "u"

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(Bad, [1, 2, 3])  # type: ignore[arg-type]
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    with pytest.raises(TypeError):
        session.feed(Measurement(1))
        session.push()


def test_ctx_record_without_recorder_raises():
    from reed import NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    ctx = NodeContext(memory=None, last_output=None)

    with pytest.raises(RuntimeError):
        ctx.record(Speed, 1.0)


def test_recording_kind_matches_the_instrument_definition():
    """Every Recording now carries a concrete kind from its Instrument
    Definition -- there is no more kind=None lazy-mode path (O7i)."""
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class EventsSeen(Instrument[int]):
        kind = InstrumentKind.COUNTER
        unit = "1"

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.record(EventsSeen, 1)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()
    session.feed(Measurement(1))
    session.push()

    recordings = session.node_session(track).recordings
    assert recordings[0].kind == "counter"
