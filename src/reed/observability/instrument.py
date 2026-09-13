"""
Instrument (Milestone O2, Slice O2a).

The logical unit of observation (docs/observability_design.md Section 18's
central sentence: "Instrument is the logical unit of observation;
Execution is the physical unit of persistence; Flow is the logical unit
of aggregation and analysis."). Declared once, not repeated per call
(docs/observability_goals.md Section 2.1).

`kind` is restricted to `"gauge"`, `"counter"`, and `"updown_counter"` for
V1 (docs/observability_non_goals.md Section 2: no `Histogram`, no OTel
Metric SDK types). `"event"` is deliberately absent here -- see Slice O2e
(docs/observability_design.md Section 19) for its resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

InstrumentKind = Literal["gauge", "counter", "updown_counter"]

_VALID_KINDS: tuple[str, ...] = get_args(InstrumentKind)


@dataclass(frozen=True, slots=True)
class Instrument:
    """
    A declared, named observable definition, owned by a Node
    (docs/observability_goals.md Section 2.1).

    `name`, `kind`, `unit`, and `description` are declared once when the
    `Instrument` is constructed -- not repeated on every `ctx.record(...)`
    call (Slice O2c).
    """

    name: str
    kind: InstrumentKind
    unit: str
    description: str = ""

    def __post_init__(self) -> None:
        if self.kind not in _VALID_KINDS:
            raise ValueError(
                f"Instrument(name={self.name!r}).kind must be one of "
                f"{_VALID_KINDS!r}, got {self.kind!r} "
                "(docs/observability_non_goals.md Section 2 -- no Histogram, "
                "no arbitrary kind values)."
            )
        if not self.name:
            raise ValueError("Instrument.name must be a non-empty string.")
