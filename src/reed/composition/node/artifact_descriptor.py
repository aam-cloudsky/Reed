"""
ArtifactDescriptor (Slice 1B, Priority 3).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1B; docs/implementation_refactor_assessment.md #11):

    ArtifactDescriptor
        domain_type
        role
        parameter_name or output name

This is intentionally minimal: it names one domain artifact's identity at
a node's signature boundary. It is NOT `ArtifactRecord` (Priority 6,
Milestone 2 slice 2C) -- it carries no value, no version, no provenance.
See `docs/non-goals.md`, "ArtifactRecord Is Not A Blind Parcel Rename",
and `docs/parcel_boundary_decision.md`:

    Domain type == artifact semantic identity
    ArtifactRecord == Reed-managed versioned record

`ArtifactDescriptor` only speaks to the first line.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ArtifactRole(Enum):
    """
    Whether an `ArtifactDescriptor` describes a consumed (dataflow input)
    or produced (dataflow output) domain artifact.
    """

    CONSUMED = auto()
    PRODUCED = auto()


@dataclass(frozen=True)
class ArtifactDescriptor:
    """
    Identity of one domain artifact at a node's signature boundary.

    `name` is the parameter name for a `CONSUMED` descriptor, or a fixed
    output name for a `PRODUCED` descriptor (see
    `domain_node_description.py`, `DomainNodeDescriptionBuilder`).
    """

    domain_type: type
    role: ArtifactRole
    name: str
