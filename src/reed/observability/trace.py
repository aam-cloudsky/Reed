"""
Level 1 -- Execution Trace (Milestone O5, Slice O5a).

docs/refactor/observability_design.md Section 11.1 splits observability into two levels with
different persistence contracts:

    Level 1 (Execution Trace / propagation): "which Node fired, in response to what,
    correlated by trace id" -- inherently observational, valuable while a Session executes
    or immediately after, but not required to be durably persisted. An in-memory ring
    buffer per Session, optionally mirrored to a plain debug log -- never a required,
    schema-committed artifact like Level 2 (Recordings/Provenance, Milestones O2-O4).

`TraceEvent` and `ExecutionTrace` are that ring buffer. They are deliberately NOT built
on top of `RecordingStore`/`ProvenanceStore` (Milestone O3) -- Level 1 has no durability
contract at all, so it needs no Protocol, no CSV schema, and no `storage_root` opt-in.
It exists purely in-process and is dropped when the `Session` is garbage-collected, unless
something (e.g. the O5b terminal renderer) is actively consuming it.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

TraceEventType = Literal["node_started", "node_finished"]


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """
    One entry in a Session's Level 1 Execution Trace.

    `event_type` is `"node_started"` (emitted immediately before a Node's function is
    called) or `"node_finished"` (emitted after its output has been committed). Both
    carry the same `node_execution_id`/`node_id`/`execution_seq` identity fields
    Recordings and Provenance events already carry (docs/refactor/observability_design.md
    Section 13.1) -- Level 1 is correlated by the same identity, not a separate one.

    This is intentionally a much thinner record than `Recording`/`ProvenanceEvent`: no
    `attributes`, no `value`, no `unit` -- Level 1 answers "what ran, in what order,
    caused by what", not "what did it observe" (that is Level 2's job).
    """

    event_type: TraceEventType
    execution_id: str
    flow_id: str
    node_id: str
    node_execution_id: str
    execution_seq: int
    timestamp: float


class ExecutionTrace:
    """
    A bounded, in-memory ring buffer of `TraceEvent`s for one `Session` (Slice O5a).

    Bounded via `collections.deque(maxlen=...)`: once `capacity` events have been
    recorded, appending a new one silently drops the oldest -- by design (Section 11.1:
    "it may be dropped when the process exits without anyone having asked for it to be
    kept"; the same reasoning extended here to "old entries may be dropped once no one
    could plausibly still want them", since Level 1 explicitly has no durability
    contract). `capacity` defaults to 1000, generous for interactive debugging/terminal
    rendering (Slice O5b) without letting a long-running `Session` grow this unboundedly.

    `.events` returns a snapshot `tuple` (not the live deque) so a caller iterating it
    is never affected by concurrent appends.
    """

    def __init__(self, *, capacity: int = 1000) -> None:
        if capacity <= 0:
            raise ValueError("ExecutionTrace capacity must be a positive integer.")
        self._capacity = capacity
        self._events: deque[TraceEvent] = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._capacity

    def record(self, event: TraceEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    def __len__(self) -> int:
        return len(self._events)
