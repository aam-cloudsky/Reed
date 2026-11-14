"""
Recording (Milestone O2, Slices O2c/O2d).

One observation of one Instrument (docs/refactor/observability_goals.md Section 1).
`value` is strictly scalar (docs/refactor/observability_non_goals.md Section 3 --
no mappings, dataclasses, lists, or nested structures; a compound fact is
multiple explicit calls with dot-segmented names, never auto-flattened).

This is the in-memory representation only (Milestone O2). Milestone O3
gives it a durable `recordings.csv` row shape; the column names chosen
here already match docs/refactor/observability_goals.md Section 6 so O3 does not
need to rename anything, only serialize it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

ScalarValue = str | int | float | bool


@dataclass(frozen=True, slots=True)
class Recording:
    """One observation of one Instrument, attached to the firing that produced it."""

    instrument_id: str
    name: str
    value: ScalarValue
    kind: str | None
    unit: str | None
    execution_id: str
    flow_id: str
    node_id: str
    node_execution_id: str
    execution_seq: int
    attributes: dict[str, ScalarValue] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
