"""
OTel exporter adapter (Milestone O6, Slice O6a).

Translates Reed's own Session/NodeExecution/Trigger events (Level 1, `ExecutionTrace`) and
`Recording`s (Level 2) into OpenTelemetry spans and metrics -- one *optional* consumer of
both levels, never a foundation Reed's core sits on top of (design record Section 8: "OTel
is an exporter target, not a foundation Reed's core sits on top of"; Section 2's own guiding
principle: "Reed defines what an execution means; OpenTelemetry provides the infrastructure
to instrument, correlate, record, and export it.").

Two consequences that follow directly from already-decided architecture, not new decisions:

    1. `opentelemetry-api`/`opentelemetry-sdk` are an optional extra (`pip install
       reed-sync[otel]`), never a core dependency -- neither `reed.observability` nor any
       other Reed module imports this module implicitly. A caller that wants OTel export
       imports `reed.observability.otel_export` itself; if the packages are not installed,
       that import raises `ModuleNotFoundError` from the standard Python import machinery,
       not a Reed-specific error -- there is nothing to catch and re-raise more helpfully
       that `pip install reed-sync[otel]` in the traceback doesn't already say.
    2. The mapping from `Instrument.kind` to an OTel metric instrument is explicit and
       kind-gated (`docs/observability_non_goals.md` Section 4: "do not infer OTel export
       mappings from Python types"). A lazy-mode `Recording` (`kind=None`, Section 19) is
       never exported as a metric -- there is no `Instrument` behind it to determine which
       OTel instrument kind it would even be. `export_recording_to_metric(...)` silently
       skips `kind=None` recordings rather than guessing.

This adapter takes an already-configured `Tracer`/`Meter` as a parameter rather than owning
any global OTel provider configuration itself (no `TracerProvider`/`MeterProvider`
construction, no `set_tracer_provider`/`set_meter_provider` calls) -- provider setup and
export destination (console, OTLP collector, ...) are the caller's concern, orthogonal to
what this module translates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from reed.observability.recording import Recording
from reed.observability.trace import ExecutionTrace

if TYPE_CHECKING:
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import Tracer

_KIND_TO_METRIC_FACTORY = {
    "gauge": "create_gauge",
    "counter": "create_counter",
    "updown_counter": "create_up_down_counter",
}

# Milestone O6, Slice O6a: one OTel metric instrument object per (meter, name),
# created once and reused -- OTel instrument creation is not free, and creating
# a fresh one per Recording would also make repeated calls with the same name
# error on some SDKs, which reject re-registering a duplicate instrument name.
_metric_instrument_cache: "dict[tuple[int, str], object]" = {}


def export_trace_to_spans(trace: ExecutionTrace, *, tracer: "Tracer") -> int:
    """
    Translate `trace`'s current `"node_started"`/`"node_finished"` pairs into
    OTel spans via `tracer.start_span(...)`/`span.end(...)`, using each
    `TraceEvent`'s own `timestamp` as the span's start/end time (nanoseconds,
    per the OTel API) rather than the wall-clock time this function happens
    to run at -- a replayed/deferred export must not misreport when a Node
    actually ran.

    Each span is named after `node_id` (Reed's own stable identity, Section
    18) and carries `execution_id`, `flow_id`, `node_execution_id`, and
    `execution_seq` as span attributes -- Reed's own identifiers become OTel's
    correlation keys for this translation (design record Section 8), never
    the reverse.

    Only complete `"node_started"`/`"node_finished"` pairs produce a span --
    a firing the ring buffer only has half of (Slice O5a: dropped past
    capacity, or the renderer/exporter ran mid-firing) has nothing well-formed
    to export and is silently skipped, matching `terminal.py`'s "running"
    row rather than fabricating an end time. Returns the number of spans
    exported.
    """
    paired: dict[str, dict[str, object]] = {}
    for event in trace.events:
        paired.setdefault(event.node_execution_id, {})[event.event_type] = event

    exported = 0
    for node_execution_id, by_type in paired.items():
        started = by_type.get("node_started")
        finished = by_type.get("node_finished")
        if started is None or finished is None:
            continue

        span = tracer.start_span(
            started.node_id,  # type: ignore[union-attr]
            start_time=int(started.timestamp * 1e9),  # type: ignore[union-attr]
        )
        span.set_attribute("reed.execution_id", started.execution_id)  # type: ignore[union-attr]
        span.set_attribute("reed.flow_id", started.flow_id)  # type: ignore[union-attr]
        span.set_attribute("reed.node_id", started.node_id)  # type: ignore[union-attr]
        span.set_attribute("reed.node_execution_id", node_execution_id)
        span.set_attribute("reed.execution_seq", started.execution_seq)  # type: ignore[union-attr]
        span.end(end_time=int(finished.timestamp * 1e9))  # type: ignore[union-attr]
        exported += 1

    return exported


def _get_metric_instrument(meter: "Meter", kind: str, name: str, unit: str) -> object:
    cache_key = (id(meter), name)
    cached = _metric_instrument_cache.get(cache_key)
    if cached is not None:
        return cached

    factory_name = _KIND_TO_METRIC_FACTORY[kind]
    factory = getattr(meter, factory_name)
    instrument = factory(name, unit=unit)
    _metric_instrument_cache[cache_key] = instrument
    return instrument


def export_recording_to_metric(recording: Recording, *, meter: "Meter") -> bool:
    """
    Translate one `Recording` into an OTel metric observation, kind-gated
    per `Instrument.kind` (`docs/observability_non_goals.md` Section 4) --
    `"gauge"` -> `meter.create_gauge(...)`, `"counter"` ->
    `meter.create_counter(...)`, `"updown_counter"` ->
    `meter.create_up_down_counter(...)`. `recording.attributes` is passed
    through unchanged as the OTel measurement's attributes.

    A lazy-mode `Recording` (`kind=None`, Slice O2e/Section 19) is not a
    metric at all -- there is no `Instrument` behind it, so there is no
    kind to map from. This function returns `False` and records nothing for
    `kind=None`, never guessing a kind from `type(recording.value)`
    (`observability_non_goals.md` Section 4's explicit prohibition).
    Returns `True` when a metric observation was recorded.
    """
    if recording.kind is None:
        return False

    instrument = _get_metric_instrument(
        meter, recording.kind, recording.name, recording.unit or ""
    )

    if recording.kind == "gauge":
        instrument.set(recording.value, attributes=recording.attributes)  # type: ignore[attr-defined]
    else:
        instrument.add(recording.value, attributes=recording.attributes)  # type: ignore[attr-defined]

    return True
