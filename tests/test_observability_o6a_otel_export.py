"""
Milestone O6, Slice O6a -- OTel exporter adapter (design record §25).

Covers docs/observability_non_goals.md Section 4 (no inference of OTel
export mappings from Python types -- kind-gated only) and design record
Section 8 (OTel is one optional consumer of Level 1/Level 2 data, never a
foundation Reed's core depends on).

Skipped entirely if opentelemetry is not installed -- it is an optional
extra (`pip install reed-sync[otel]`), never a core Reed dependency.
"""

from __future__ import annotations

import pytest

otel_sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
otel_sdk_metrics = pytest.importorskip("opentelemetry.sdk.metrics")

from opentelemetry.sdk.metrics import MeterProvider  # noqa: E402
from opentelemetry.sdk.metrics.export import InMemoryMetricReader  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)


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


class Hits(Instrument[int]):
    kind = InstrumentKind.COUNTER
    unit = "1"


def _make_tracer():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer("reed-test"), exporter


def _make_meter():
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    return provider.get_meter("reed-test"), reader


def test_export_trace_to_spans_translates_started_finished_pairs():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(produce)
    run = flow.run()
    run.publish(Measurement(1))

    tracer, exporter = _make_tracer()

    from reed.observability.otel_export import export_trace_to_spans

    count = export_trace_to_spans(run.trace, tracer=tracer)
    spans = exporter.get_finished_spans()

    assert count == 1
    assert len(spans) == 1
    assert spans[0].name.endswith("produce")
    assert spans[0].attributes["reed.execution_id"] == run.execution_id
    assert spans[0].attributes["reed.flow_id"] == run.flow_id


def test_export_trace_to_spans_skips_incomplete_pairs():
    from reed.observability.otel_export import export_trace_to_spans
    from reed.observability.trace import ExecutionTrace, TraceEvent

    trace = ExecutionTrace()
    trace.record(
        TraceEvent(
            event_type="node_started",
            execution_id="exec",
            flow_id="flow",
            node_id="mod.node",
            node_execution_id="ne-1",
            execution_seq=1,
            timestamp=0.0,
        )
    )

    tracer, exporter = _make_tracer()
    count = export_trace_to_spans(trace, tracer=tracer)

    assert count == 0
    assert exporter.get_finished_spans() == ()


def test_export_recording_to_metric_gauge():
    from reed import Flow, NodeContext
    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()
    run.publish(Measurement(7))

    recording = run.node_runtime(track).recordings[0]

    meter, reader = _make_meter()

    from reed.observability.otel_export import export_recording_to_metric

    exported = export_recording_to_metric(recording, meter=meter)
    assert exported is True

    data = reader.get_metrics_data()
    metric = data.resource_metrics[0].scope_metrics[0].metrics[0]
    assert metric.name == Speed.instrument_name().lower()  # OTel lowercases metric names
    assert metric.data.data_points[0].value == 7


def test_export_recording_to_metric_skips_kind_none():
    """
    O7i removed the old lazy-mode plain-string ctx.record(...) path that
    used to produce Recording.kind=None -- every Instrument now has a
    concrete kind. `export_recording_to_metric` must still skip a
    kind=None Recording if one exists (e.g. constructed directly, or by
    a future non-Instrument-backed observation path) -- this is a
    contract test against `Recording` itself, not against any live
    ctx.record(...) call.
    """
    from reed.observability.recording import Recording

    recording = Recording(
        instrument_id="flow.node.reason",
        name="reason",
        value="no prior signal",
        kind=None,
        unit=None,
        execution_id="exec",
        flow_id="flow",
        node_id="node",
        node_execution_id="ne-1",
        execution_seq=1,
    )

    meter, reader = _make_meter()

    from reed.observability.otel_export import export_recording_to_metric

    exported = export_recording_to_metric(recording, meter=meter)
    assert exported is False

    data = reader.get_metrics_data()
    assert data is None


def test_export_recording_to_metric_counter():
    from reed import Flow, NodeContext
    def track(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Hits, 1)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()
    run.publish(Measurement(1))

    recording = run.node_runtime(track).recordings[0]
    meter, reader = _make_meter()

    from reed.observability.otel_export import export_recording_to_metric

    export_recording_to_metric(recording, meter=meter)

    data = reader.get_metrics_data()
    metric = data.resource_metrics[0].scope_metrics[0].metrics[0]
    assert metric.name == Hits.instrument_name().lower()  # OTel lowercases metric names
