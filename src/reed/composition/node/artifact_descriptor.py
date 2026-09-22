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

Slice 21A (GitHub issue #21, "Distinguish triggering inputs from sampled
inputs in node firing rules") adds `InputRole` and a defaulted
`input_role` field, purely additive: every existing construction site
keeps working unchanged because the field defaults to
`InputRole.TRIGGERING`, today's only behavior. See
`references/ingested/reed-refactor-protocol-recovered-reference.md` and
`reed-sampled-inputs-proposal.md` for the full motivation; Slice 21B
wires detection of `Annotated[T, Sampled]` into this field, and Slice
21C changes how `Session` reads it for firing eligibility.
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


class InputRole(Enum):
    """
    Whether a CONSUMED `ArtifactDescriptor` counts toward a `FlowNode`'s
    firing eligibility, or only toward its argument coverage (Slice
    21A/21B/21C, GitHub issue #21).

    TRIGGERING is the only role that existed before this issue and
    remains the default: an arriving value of a TRIGGERING type can make
    its `FlowNode` eligible to fire (subject to `TriggerPolicy`,
    `Session._is_eligible_to_fire`). SAMPLED marks a consumed parameter,
    declared via `Annotated[T, Sampled]` (Slice 21B,
    `reed.composition.node.sampled.Sampled`), whose latest committed
    value the node still needs to be called -- it still counts toward
    `Session._is_fully_covered` -- but whose own arrival must never by
    itself make the node eligible to fire (Slice 21C).

    Meaningless for a PRODUCED descriptor: `DomainNodeDescriptionBuilder`
    always leaves a produced artifact's `input_role` at its default,
    `TRIGGERING`, since firing eligibility is a property of a node's
    consumed side only.

    Deliberately just these two members -- the proposal underlying issue
    #21 scopes this to TRIGGERING/SAMPLED only; a third role is
    undesigned, future work, not something to speculatively add here.
    """

    TRIGGERING = auto()
    SAMPLED = auto()


@dataclass(frozen=True)
class ArtifactDescriptor:
    """
    Identity of one domain artifact at a node's signature boundary.

    `name` is the parameter name for a `CONSUMED` descriptor, or a fixed
    output name for a `PRODUCED` descriptor (see
    `domain_node_description.py`, `DomainNodeDescriptionBuilder`).

    `input_role` (Slice 21A) is a defaulted, keyword-compatible field
    added after the original three: every pre-existing positional or
    keyword construction of the first three fields keeps working
    unchanged, and equality/hashing (this dataclass is frozen, so both
    are generated from all four fields) only changes for a descriptor
    that explicitly sets `input_role=InputRole.SAMPLED` -- every
    pre-existing descriptor, which never set it, compares and hashes
    exactly as before against another descriptor that also leaves it at
    the default.
    """

    domain_type: type
    role: ArtifactRole
    name: str
    input_role: InputRole = InputRole.TRIGGERING
