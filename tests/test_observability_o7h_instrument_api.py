"""
Milestone O7 -- Instrument declared-mode API self-containment audit
(design record: name-based resolution vs. Instrument-object resolution).

Prompted by the acceptance example: `ctx.record(temperature, value)` required
the Node body to import/reference the same module-level `Instrument` object
also passed to `flow.add(..., instruments=[temperature])` -- duplicating the
dependency and coupling the Node function to a global. `NodeRuntime.
_resolve_instrument(...)` already supported a plain string name in declared
mode (`ctx.record("temperature", value)`), resolving purely against the
FlowNode's own declared schema with no Instrument object needed inside the
Node body at all -- but passing an `Instrument` *object* silently bypassed
that schema entirely, trusting the passed object's own kind/unit with no
cross-check against what was actually declared. That is the real defect
this file guards against: an ad hoc Instrument object could contradict, or
entirely sidestep, the FlowNode's declared instruments.
"""

from __future__ import annotations

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_declared_mode_by_name_needs_no_instrument_object_in_the_node_body():
    """
    The self-contained style: the Node function references only a plain
    string name, never the Instrument object -- the schema lives entirely
    in `flow.add(..., instruments=[...])`.
    """
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    temperature = Instrument(name="temperature", kind="gauge", unit="celsius")

    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record("temperature", measurement.value)  # no Instrument import needed
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[temperature])
    run = flow.run()
    run.publish(Measurement(91.3))

    recording = run.node_runtime(track).recordings[0]
    assert recording.name == "temperature"
    assert recording.kind == "gauge"
    assert recording.unit == "celsius"


def test_instrument_object_matching_the_declaration_still_works():
    """Backward compatible: passing the same declared Instrument object works identically."""
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    temperature = Instrument(name="temperature", kind="gauge", unit="celsius")

    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(temperature, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[temperature])
    run = flow.run()
    run.publish(Measurement(1))

    recording = run.node_runtime(track).recordings[0]
    assert recording.kind == "gauge"


def test_instrument_object_mismatching_the_declared_kind_is_rejected():
    """
    An ad hoc Instrument object whose kind/unit contradicts what was
    actually declared for that name must raise, not silently win.
    """
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    declared = Instrument(name="temperature", kind="gauge", unit="celsius")
    mismatched = Instrument(name="temperature", kind="counter", unit="celsius")

    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(mismatched, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[declared])
    run = flow.run()

    with pytest.raises(ValueError):
        run.publish(Measurement(1))


def test_undeclared_instrument_object_is_rejected_even_though_it_is_a_real_instrument():
    """
    An Instrument object that was never passed to flow.add(instruments=[...])
    at all must not be usable to sidestep declared-mode validation.
    """
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    declared = Instrument(name="temperature", kind="gauge", unit="celsius")
    rogue = Instrument(name="rogue", kind="gauge", unit="celsius")

    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(rogue, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, instruments=[declared])
    run = flow.run()

    with pytest.raises(ValueError):
        run.publish(Measurement(1))
