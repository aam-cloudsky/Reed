# ---------------------------------------------------------------------
# Event Monitor
# ---------------------------------------------------------------------


from dataclasses import dataclass

from reed.transportation.observability.trace import TraceRecord, TraceState


class MonitorEvent:
    pass


@dataclass
class TraceEvent(MonitorEvent):
    trace: TraceRecord
    state: TraceState
