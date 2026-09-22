"""
Structured logging (Milestone O8, Slice O8a).

A `LogEvent` is a stable, named-field *projection* of a fact Reed's existing
observability model already collected at Issue #7's semantic boundaries --
`NodeExecutionIdentity`, `ProvenanceEvent` ("generated"/"used"), `Recording`, and a
Node firing's own duration/error bookkeeping. It is never an independent source of
truth: nothing here computes or stores anything Reed did not already commit via
`ExecutionTrace`/`ProvenanceStore`/`RecordingStore` (see docs/logging_design.md Section
3). `StructuredLogPresenter` builds one `LogEvent` per `Presenter` hook call it
receives and hands its `to_dict()` to a sink callable -- by default, one JSON line
printed to stdout.

This module intentionally shares the `Presenter` Protocol (`reed.observability.
presenter`) as its only integration point with `Session` -- there is no second hook
mechanism, no new `Session`-facing concept. See `CompositePresenter` in `presenter.py` for
how a `Session` can drive both a `TerminalPresenter` and a `StructuredLogPresenter` from the
one `Presenter` it holds.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Callable, Literal

from reed.observability.presenter import Presenter

if TYPE_CHECKING:
    from reed.observability.identity import NodeExecutionIdentity
    from reed.observability.recording import Recording, ScalarValue

Severity = Literal["info", "warning", "error"]

# A small, closed vocabulary (mirrors `Instrument.kind`'s own closed-set reasoning,
# docs/observability_goals.md) -- never a free-form string a caller can invent.
EventName = Literal[
    "node_started",
    "node_finished",
    "node_error",
    "artifact_generated",
    "artifact_consumed",
    "instrument_recorded",
]


@dataclass(frozen=True, slots=True)
class LogEvent:
    """
    One structured log event. Base fields are always present; event-specific
    fields are `None` unless `event` is the kind that fills them in (Section 5 of
    docs/logging_design.md). `to_dict()` drops every `None`-valued field so the
    serialized shape only ever shows fields meaningful for that `event`.
    """

    timestamp: float
    severity: Severity
    event: EventName
    execution_id: str
    flow_id: str
    node_id: str | None = None
    node_execution_id: str | None = None

    duration: float | None = None
    error_type: str | None = None
    error_message: str | None = None

    artifact_type: str | None = None
    artifact_version: int | None = None

    instrument_name: str | None = None
    value: "ScalarValue | None" = None
    unit: str | None = None
    kind: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _from_identity(
    identity: "NodeExecutionIdentity", *, event: EventName, severity: Severity = "info", **fields: object
) -> LogEvent:
    return LogEvent(
        timestamp=time.time(),
        severity=severity,
        event=event,
        execution_id=identity.execution_id,
        flow_id=identity.flow_id,
        node_id=identity.node_id,
        node_execution_id=identity.node_execution_id,
        **fields,
    )


class StructuredLogPresenter(Presenter):
    """
    A `Presenter` (Issue #7's existing hook Protocol) that turns each hook call
    into a `LogEvent` and passes its `to_dict()` to `sink` -- default: one JSON
    line to stdout, the simplest possible structured sink. Any other sink (a
    file, a queue, a future OTel Logs adapter) is a different `sink` callable,
    never a change to this class or to `Session`.

    Composes with `TerminalPresenter` via `CompositePresenter`
    (`reed.observability.presenter`) so a `Session` can render for humans and emit
    structured events at the same time, from the same underlying facts.
    """

    def __init__(self, *, sink: "Callable[[dict[str, object]], None] | None" = None) -> None:
        self._sink = sink or self._default_sink

    @staticmethod
    def _default_sink(payload: dict[str, object]) -> None:
        print(json.dumps(payload), file=sys.stdout)

    def _emit(self, event: LogEvent) -> None:
        self._sink(event.to_dict())

    def on_node_started(self, identity: "NodeExecutionIdentity", *, depth: int = 0) -> None:
        self._emit(_from_identity(identity, event="node_started"))

    def on_node_finished(
        self, identity: "NodeExecutionIdentity", *, depth: int = 0, duration: float
    ) -> None:
        self._emit(_from_identity(identity, event="node_finished", duration=duration))

    def on_node_error(
        self, identity: "NodeExecutionIdentity", exc: BaseException, *, duration: float
    ) -> None:
        self._emit(
            _from_identity(
                identity,
                event="node_error",
                severity="error",
                duration=duration,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        )

    def on_artifact_generated(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        self._emit(
            _from_identity(
                identity,
                event="artifact_generated",
                artifact_type=artifact_type,
                artifact_version=artifact_version,
            )
        )

    def on_artifact_consumed(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        self._emit(
            _from_identity(
                identity,
                event="artifact_consumed",
                artifact_type=artifact_type,
                artifact_version=artifact_version,
            )
        )

    def on_recording(self, recording: "Recording") -> None:
        self._emit(
            LogEvent(
                timestamp=recording.timestamp,
                severity="info",
                event="instrument_recorded",
                execution_id=recording.execution_id,
                flow_id=recording.flow_id,
                node_id=recording.node_id,
                node_execution_id=recording.node_execution_id,
                instrument_name=recording.name,
                value=recording.value,
                unit=recording.unit,
                kind=recording.kind,
            )
        )
