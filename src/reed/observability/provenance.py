"""
ProvenanceEvent (Milestone O4, Slice O4a).

A normalized W3C-PROV-style event: `"generated"` (a Node produced an
Artifact) or `"used"` (a Node consumed an Artifact) -- never a wide
producer/consumer row (docs/refactor/observability_design.md Section 8, Round 4).
A producer/consumer graph is reconstructed by grouping on
`(artifact_id, artifact_version, instance_id)` at query time (Slice MI-J,
docs/refactor/multi_instance_execution_plan.md, Risk R5 -- `instance_id`
added to the group-by key so two different artifact instances' own first
commits of the same type, each independently starting its own version
sequence at 1, never collide into one graph node).
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
    instance_id: str = "<InstanceKey.singleton>"
    timestamp: float = field(default_factory=time.time)
