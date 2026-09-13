"""
Milestone O7, Slices O7d/O7e -- terminal presentation policy/API.

Covers:

    - silent produces no Reed terminal output;
    - errors-only suppresses normal execution output;
    - instruments-only does not expose graph propagation;
    - nodes mode shows Node executions;
    - verbose mode exposes propagation;
    - progress mode renders without a false fraction (no "N/M" claim);
    - invalid configuration fails clearly;
    - presentation choice does not change execution semantics;
    - presentation choice does not disable persistence/provenance unless
      separately configured (storage_root=... is independent of
      observability=...).
"""

from __future__ import annotations

import pytest
from rich.console import Console


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


from reed.observability.instrument import Instrument, InstrumentKind


class Speed(Instrument[int]):
    kind = InstrumentKind.GAUGE
    unit = "m/s"


def _make_flow():
    from reed import Flow, NodeContext

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def _console_output(flow, observability, publish_value=None) -> str:
    from reed.observability.presentation import resolve_presentation_policy
    from reed.observability.presenter import build_presenter

    console = Console(record=True, width=200)
    policy = resolve_presentation_policy(observability)
    presenter = build_presenter(policy, console=console)

    run = flow.run()
    run._presenter = presenter  # test-only: swap in a recording console
    run.publish(publish_value or Measurement(1))
    return console.export_text()


def test_silent_produces_no_terminal_output():
    flow, produce = _make_flow()
    output = _console_output(flow, "silent")
    assert output.strip() == ""


def test_errors_only_suppresses_normal_execution_output():
    flow, produce = _make_flow()
    output = _console_output(flow, "errors")
    # No node checkmark, no propagation, no instrument line -- errors mode
    # is silent on the success path.
    assert output.strip() == ""


def test_errors_only_reports_a_node_error():
    from reed import Flow, NodeContext
    from reed.observability.presentation import resolve_presentation_policy
    from reed.observability.presenter import build_presenter

    def failing(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        raise RuntimeError("boom")

    flow = Flow()
    flow.add(failing)

    console = Console(record=True, width=200)
    presenter = build_presenter(resolve_presentation_policy("errors"), console=console)
    run = flow.run()
    run._presenter = presenter

    with pytest.raises(RuntimeError):
        run.publish(Measurement(1))

    output = console.export_text()
    assert "ERROR" in output
    assert "failing" in output


def test_instruments_mode_does_not_expose_propagation():
    flow, produce = _make_flow()
    output = _console_output(flow, "instruments")
    assert Speed.instrument_name() in output
    assert "->" not in output  # no propagation arrows


def test_nodes_mode_shows_node_executions():
    flow, produce = _make_flow()
    output = _console_output(flow, "nodes")
    assert "produce" in output


def test_verbose_mode_exposes_propagation_and_instruments_and_timings():
    flow, produce = _make_flow()
    output = _console_output(flow, "verbose")
    assert "produce" in output
    assert Speed.instrument_name() in output
    assert "ms" in output  # timings dimension


def test_progress_mode_never_claims_a_false_fraction():
    flow, produce = _make_flow()
    output = _console_output(flow, "progress")
    import re

    assert not re.search(r"\d+\s*/\s*\d+", output), (
        "progress must never render a N/M fraction -- Reed cannot know the "
        "true denominator in a reactive graph"
    )


def test_invalid_preset_name_fails_clearly():
    from reed.observability.presentation import resolve_presentation_policy

    with pytest.raises(ValueError):
        resolve_presentation_policy("nonexistent-preset")


def test_presentation_choice_does_not_change_execution_semantics():
    """The exact same domain result, regardless of observability= value."""
    results = {}
    for mode in ("silent", "errors", "progress", "instruments", "nodes", "verbose"):
        flow, produce = _make_flow()
        run = flow.run(observability=mode)
        results[mode] = run.publish(Measurement(7)).value

    assert len(set(results.values())) == 1
    assert results["silent"] == 7


def test_silent_terminal_does_not_disable_persistence_or_provenance(tmp_path):
    """
    terminal: silent, recordings: persisted, provenance: persisted --
    a silent terminal must not be conflated with "stop collecting."
    """
    flow, produce = _make_flow()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root), observability="silent")
    run.publish(Measurement(1))

    from reed.observability.replay import load_provenance, load_recordings

    run_dir = root / "runs" / run.execution_id
    assert len(load_recordings(run_dir)) == 1
    assert len(load_provenance(run_dir)) >= 1


def test_default_observability_is_not_silent():
    """Flow.run() with no observability= argument still shows node lifecycle."""
    flow, produce = _make_flow()
    output = _console_output(flow, None)
    assert "produce" in output
