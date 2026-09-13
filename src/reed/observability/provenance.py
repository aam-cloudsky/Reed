"""
ProvenanceEvent (Milestone O4, Slice O4a).

A normalized W3C-PROV-style event: `"generated"` (a Node produced an
Artifact) or `"used"` (a Node consumed an Artifact) -- never a wide
producer/consumer row (docs/observability_design.md Section 8, Round 4).
A producer/consumer graph is reconstructed by grouping on
`(artifact_id, artifact_version)` at query time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

ProvenanceEventType = Literal["generated", "used"]


@dataclass(frozen=True, slots=True)
class ProvenanceEvent:
    """One normalized provenance event row."""

    event_type: ProvenanceEventType
    artifact_id: str
    artifact_version: int
    node_execution_id: str
    node_id: str
    execution_seq: int
    timestamp: float = field(default_factory=time.time)
