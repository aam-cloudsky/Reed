"""
Milestone O7 -- Instrument declared-mode API self-containment audit
(superseded by Milestone O7, Slice O7i).

This slice originally investigated the tension between a Node needing to
reference a shared `Instrument` object for `ctx.record(...)` while that
same object also had to be threaded through `flow.add(...,
instruments=[...])` -- and fixed a real validation gap where an ad hoc
`Instrument` object could bypass a FlowNode's declared schema entirely.

Slice O7i's typed-Instrument redesign (`reed.observability.instrument`)
supersedes this whole API: there is no more `flow.add(...,
instruments=[...])` parameter, no more `Instrument` instances at all (only
subclasses, used as values, never instantiated), and therefore no more
"declared vs. undeclared" or "matches the declaration vs. mismatches it"
distinction to guard against -- `ctx.record(SomeInstrument, value)`
references the Instrument Definition directly and exclusively; there is
no second declaration anywhere to duplicate or contradict. This file is
kept (rather than deleted) to preserve the historical record of what O7h
found and why O7i's redesign is a strictly stronger resolution of the
same self-containment concern; see docs/observability_design.md Round 18
(Section 30) and Round 22 (Section 34) for the full rationale.

See test_observability_o2_instrument_recording.py for current coverage of
`ctx.record(SomeInstrument, value)`'s self-contained, single-reference
behavior.
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_a_node_references_its_instrument_exactly_once_no_separate_declaration():
    """
    The self-containment property O7h originally investigated for the old
    API is now structural, not merely a preferred style: there is no
    `instruments=[...]` parameter left to duplicate the reference into.
    """
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument, InstrumentKind

    class Temperature(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "celsius"

    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Temperature, float(measurement.value))
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)  # no instruments= parameter exists anymore
    session = flow.session()
    session.feed(Measurement(91))
    session.push()

    recording = session.node_session(track).recordings[0]
    assert recording.name == Temperature.instrument_name()
    assert recording.kind == "gauge"
    assert recording.unit == "celsius"
