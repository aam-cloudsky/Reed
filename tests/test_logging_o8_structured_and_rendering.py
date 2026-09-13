"""
Milestone O8 -- structured logging and terminal rendering behavioral harness.

Covers (Issue #8 Phase 4):

    - single publication (Node -> Artifact -> Repository) renders compactly
      in normal (propagation) mode;
    - multi-hop propagation renders each hop in order;
    - repeated publication shows artifact versions correctly (@v1, @v2, ...);
    - instrument recording appears only at the appropriate presentation
      level (compact vs. verbose);
    - failure remains visible per policy, and a broken renderer cannot
      affect computation -- mirrors O7g's Presenter-isolation test, extended
      to `CompositePresenter`;
    - silent mode leaves computation/observation unchanged with no human
      output, and does not disable structured logging (a separate sink);
    - verbose mode shows more detail (explicit CONSUME/RECORD/COMMIT
      operations) without changing semantics;
    - the structured `LogEvent` representation is independently testable,
      built and asserted on as dicts -- never by scraping ANSI terminal
      bytes.
"""

from __future__ import annotations

from rich.console import Console

from reed import Flow, NodeContext


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class Refined:
    def __init__(self, value: int) -> None:
        self.value = value


def _console_output(flow, observability, publish_value) -> str:
    from reed.observability.presentation import resolve_presentation_policy
    from reed.observability.presenter import build_presenter

    console = Console(record=True, width=200)
    policy = resolve_presentation_policy(observability)
    presenter = build_presenter(policy, console=console)

    run = flow.run()
    run._presenter = presenter
    run.publish(publish_value)
    return console.export_text()


# ---------------------------------------------------------------------------
# Single publication / normal-mode compactness
# ---------------------------------------------------------------------------


def _single_hop_flow():
    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce)
    return flow


def test_single_publication_renders_compactly_in_normal_mode():
    flow = _single_hop_flow()
    output = _console_output(flow, "propagation", Measurement(3))

    assert "Estimate@v1" in output
    assert "REPOSITORY" in output
    assert "produce" in output
    # Normal mode never spells out the operation word -- it is implied by
    # the arrow/column structure (docs/observability_invariants.md #33).
    assert "COMMIT" not in output
    assert "fired" not in output
    assert "published" not in output
    assert "[INFO]" not in output


def test_silent_mode_produces_no_output_but_still_computes():
    flow = _single_hop_flow()
    output = _console_output(flow, "silent", Measurement(3))
    assert output.strip() == ""


# ---------------------------------------------------------------------------
# Multi-hop propagation
# ---------------------------------------------------------------------------


def _multi_hop_flow():
    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    def refine(estimate: Estimate) -> Refined:
        return Refined(estimate.value + 1)

    flow = Flow()
    flow.add(produce)
    flow.add(refine)
    return flow


def test_multi_hop_propagation_renders_in_order():
    flow = _multi_hop_flow()
    output = _console_output(flow, "propagation", Measurement(3))

    estimate_pos = output.index("Estimate@v1")
    refined_pos = output.index("Refined@v1")
    assert estimate_pos < refined_pos, "propagation must render hops in observation order"


# ---------------------------------------------------------------------------
# Repeated publication -> artifact versions
# ---------------------------------------------------------------------------


def test_repeated_publication_shows_artifact_versions():
    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    from reed.observability.presentation import resolve_presentation_policy
    from reed.observability.presenter import build_presenter

    console = Console(record=True, width=200)
    presenter = build_presenter(resolve_presentation_policy("propagation"), console=console)
    run = flow.run()
    run._presenter = presenter
    run.publish(Measurement(1))
    run.publish(Measurement(2))
    run.publish(Measurement(3))

    output = console.export_text()
    assert "Estimate@v1" in output
    assert "Estimate@v2" in output
    assert "Estimate@v3" in output


# ---------------------------------------------------------------------------
# Instrument recording at appropriate presentation levels
# ---------------------------------------------------------------------------


def _instrumented_flow():
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow, Speed


def test_instrument_recording_absent_without_instruments_dimension():
    flow, Speed = _instrumented_flow()
    output = _console_output(flow, "propagation", Measurement(5))
    assert Speed.instrument_name() not in output


def test_instrument_recording_present_with_instruments_dimension():
    flow, Speed = _instrumented_flow()
    output = _console_output(flow, "instruments", Measurement(5))
    assert Speed.instrument_name() in output


def test_verbose_mode_shows_explicit_operations():
    flow, Speed = _instrumented_flow()
    output = _console_output(flow, "verbose", Measurement(5))
    assert "COMMIT" in output
    assert "RECORD" in output
    assert Speed.instrument_name() in output


def test_normal_propagation_mode_omits_explicit_operations():
    flow, Speed = _instrumented_flow()
    output = _console_output(flow, "propagation", Measurement(5))
    assert "COMMIT" not in output
    assert "CONSUME" not in output


# ---------------------------------------------------------------------------
# Failure isolation (mirrors O7g, extended to CompositePresenter)
# ---------------------------------------------------------------------------


def test_broken_composite_sub_presenter_does_not_affect_others_or_computation():
    from reed.observability.presenter import CompositePresenter, Presenter, TerminalPresenter
    from reed.observability.presentation import resolve_presentation_policy

    class BrokenPresenter(Presenter):
        def on_artifact_generated(self, identity, *, artifact_type, artifact_version):
            raise RuntimeError("boom: broken sub-presenter")

    console = Console(record=True, width=200)
    terminal = TerminalPresenter(resolve_presentation_policy("propagation"), console=console)
    composite = CompositePresenter([BrokenPresenter(), terminal])

    flow = _single_hop_flow()
    run = flow.run(observability="silent")
    run._presenter = composite

    result = run.publish(Measurement(4))

    assert isinstance(result, Estimate)
    assert result.value == 8
    # The healthy sub-presenter still rendered despite the broken one.
    assert "Estimate@v1" in console.export_text()


def test_error_remains_visible_and_broken_renderer_cannot_break_execution():
    from reed.observability.presenter import Presenter

    class BrokenPresenter(Presenter):
        def on_node_error(self, identity, exc, *, duration):
            raise RuntimeError("boom: renderer itself is broken")

    def failing(measurement: Measurement) -> Estimate:
        raise ValueError("node failure")

    flow = Flow()
    flow.add(failing)
    run = flow.run(observability="silent")
    run._presenter = BrokenPresenter()

    import pytest

    with pytest.raises(ValueError, match="node failure"):
        run.publish(Measurement(1))


# ---------------------------------------------------------------------------
# Structured LogEvent representation, independent of terminal strings
# ---------------------------------------------------------------------------


def test_structured_log_presenter_emits_stable_field_events():
    from reed.observability.logging import StructuredLogPresenter

    events: list[dict] = []
    sink_presenter = StructuredLogPresenter(sink=events.append)

    flow = _single_hop_flow()
    run = flow.run(observability="silent")
    run._presenter = sink_presenter
    run.publish(Measurement(3))

    event_names = {e["event"] for e in events}
    assert "node_started" in event_names
    assert "node_finished" in event_names
    assert "artifact_generated" in event_names

    generated = next(e for e in events if e["event"] == "artifact_generated")
    assert generated["artifact_type"] == "Estimate"
    assert generated["artifact_version"] == 1
    assert "execution_id" in generated
    assert "flow_id" in generated
    assert "node_id" in generated
    assert "node_execution_id" in generated
    # No terminal/ANSI concerns leak into the structured representation.
    assert "\x1b" not in str(generated)


def test_structured_log_presenter_reports_errors_with_error_severity():
    from reed.observability.logging import StructuredLogPresenter

    events: list[dict] = []

    def failing(measurement: Measurement) -> Estimate:
        raise RuntimeError("boom")

    flow = Flow()
    flow.add(failing)
    run = flow.run(observability="silent")
    run._presenter = StructuredLogPresenter(sink=events.append)

    try:
        run.publish(Measurement(1))
    except RuntimeError:
        pass

    error_events = [e for e in events if e["event"] == "node_error"]
    assert len(error_events) == 1
    assert error_events[0]["severity"] == "error"
    assert error_events[0]["error_type"] == "RuntimeError"


def test_detail_level_never_changes_computation():
    """Same domain result regardless of observability=/detail level -- terminal
    and structured-logging configuration is purely additive."""
    results = {}
    for mode in ("silent", "errors", "progress", "instruments", "nodes", "propagation", "verbose"):
        flow = _single_hop_flow()
        run = flow.run(observability=mode)
        results[mode] = run.publish(Measurement(7)).value

    assert len(set(results.values())) == 1
    assert next(iter(results.values())) == 14


def test_composite_presenter_lets_structured_logging_run_even_when_terminal_is_silent():
    """Disabling terminal output never disables structured logging (invariant #36)."""
    from reed.observability.logging import StructuredLogPresenter
    from reed.observability.presenter import CompositePresenter, NullPresenter

    events: list[dict] = []
    composite = CompositePresenter([NullPresenter(), StructuredLogPresenter(sink=events.append)])

    flow = _single_hop_flow()
    run = flow.run(observability="silent")
    run._presenter = composite
    run.publish(Measurement(2))

    assert any(e["event"] == "artifact_generated" for e in events)
