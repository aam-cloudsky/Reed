"""
Milestone O7, Slice O7g -- final invariant audit finding: Presenter hook
failures must never change application semantics (architectural invariant
#25, extended from Recording/Provenance store failures to the new O7d/O7e
Presenter hooks, which are also observability -- purely additive terminal
output -- and must be held to the same isolation guarantee).
"""

from __future__ import annotations


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
    return flow


def test_presenter_hook_failure_does_not_break_publish():
    from reed.observability.presenter import Presenter

    class BrokenPresenter(Presenter):
        def on_node_started(self, identity, *, depth=0):
            raise RuntimeError("boom: presenter is broken")

    flow = _make_flow()
    run = flow.run(observability="silent")
    # Force a broken presenter onto the Run to simulate a rendering
    # failure (e.g. a Rich/Console error) without needing a real broken
    # terminal.
    run._presenter = BrokenPresenter()

    result = run.publish(Measurement(3))

    assert isinstance(result, Estimate)
    assert result.value == 6


def test_presenter_hook_failure_does_not_break_recording():
    from reed.observability.presenter import Presenter

    class BrokenPresenter(Presenter):
        def on_recording(self, recording):
            raise RuntimeError("boom: presenter is broken on recording")

    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class ValueInstrument(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "1"

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(ValueInstrument, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    run = flow.run(observability="silent")
    run._presenter = BrokenPresenter()

    result = run.publish(Measurement(5))

    assert isinstance(result, Estimate)
    assert result.value == 5
