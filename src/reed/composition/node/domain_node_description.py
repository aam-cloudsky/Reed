"""
Domain-typed NodeDescription / NodeDefinition (Slice 1B, Priority 2).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1B; docs/architectural_decision.md, "Node Definition"):

    NodeDefinition
        reusable typed callable definition
        owns no flow-local policy
        owns no callback
        owns no execution state

    NodeDescription
        stores domain artifact input descriptors
        stores domain artifact output descriptor
        stores optional NodeContext descriptor

This module builds `DomainNodeDescription`/`DomainNodeDefinition` on top
of Slice 1A's `DomainNodeSignatureParser` (`domain_signature.py`): all
signature validation (self-flow rejection, NodeContext detection and
output-type checking, missing-annotation/async/varargs rejection) is
performed there and reused here, not duplicated.

This is additive alongside the existing Parcel-centric
`NodeDescription`/`NodeDefinition` (`reed.composition.node.node_definition`),
which remains the current, regression-protected path (see
`docs/refactor_state.md`, Known Compatibility Layer). The two are not
merged in this slice -- see the Rename Rule in
`docs/refactor_agent_protocol.md`: "First make the boundary real. Then
rename the boundary." `DomainNodeDefinition` deliberately carries no
`propagation_policy`/`trigger_policy`/`on_output` field: that ownership
belongs to `FlowNode` (Priority 9 / 10, Slice 1C / 1E), not to the node
definition (architectural_invariants.md #1, #5).

`NodeKind` (INPUT/TRANSFORM/OUTPUT) has no equivalent here: the target
architecture (docs/parcel_boundary_decision.md) treats every node
uniformly as consuming and producing domain artifact types; Flow infers
topology and role from the type graph, not from a declared node kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from reed.composition.node.artifact_descriptor import (
    ArtifactDescriptor,
    ArtifactRole,
    InputRole,
)
from reed.composition.node.domain_signature import DomainNodeSignatureParser


@dataclass(frozen=True)
class NodeContextDescriptor:
    """
    Descriptor for an optional injected `NodeContext` parameter.

    Kept separate from `ArtifactDescriptor`: `NodeContext != InputPort`
    (architectural_invariants.md #12), so it must never be mistaken for a
    dataflow artifact descriptor.
    """

    parameter_name: str
    memory_type: type
    output_type: type


@dataclass(frozen=True)
class DomainNodeDescription:
    """
    Structural description derived from a typed domain node function.

    See module docstring for the exact Slice 1B scope.
    """

    function: Callable
    consumed_artifacts: tuple[ArtifactDescriptor, ...]
    produced_artifact: ArtifactDescriptor
    context: NodeContextDescriptor | None


@dataclass(frozen=True)
class DomainNodeDefinition:
    """
    Reusable, domain-typed node definition.

    Owns no flow-local policy, no callback, and no execution state -- see
    module docstring.
    """

    description: DomainNodeDescription

    @property
    def function(self) -> Callable:
        return self.description.function

    @property
    def name(self) -> str:
        return self.function.__name__


class DomainNodeDescriptionBuilder:
    """
    Builds a `DomainNodeDescription` from a typed domain callable.

    Reuses `DomainNodeSignatureParser` (Slice 1A) for all signature
    parsing and validation; this builder only shapes that result into
    `ArtifactDescriptor` / `NodeContextDescriptor` instances. It does not
    re-implement or duplicate validation.
    """

    _PRODUCED_NAME = "return"

    def __init__(
        self,
        function: Callable,
        *,
        extra_globalns: dict[str, object] | None = None,
    ) -> None:
        # Slice 1F addition: see domain_signature.py's module docstring
        # for why this exists (annotation names visible only in the
        # immediate caller's local scope).
        self._function = function
        self._extra_globalns = extra_globalns

    def build(self) -> DomainNodeDescription:
        parsed_signature = DomainNodeSignatureParser(
            self._function, extra_globalns=self._extra_globalns
        ).parse()

        consumed_artifacts = tuple(
            ArtifactDescriptor(
                domain_type=parameter_type,
                role=ArtifactRole.CONSUMED,
                name=parameter_name,
                # Slice 21B: a parameter annotated Annotated[T, Sampled]
                # (detected by DomainNodeSignatureParser, Slice 21B) gets
                # InputRole.SAMPLED. Slice MI-H: a parameter annotated
                # Annotated[T, Collective] also gets InputRole.SAMPLED --
                # a collective dependency's own arrival must never by
                # itself make its node eligible to fire (see
                # reed.composition.node.collective.Collective's own
                # docstring) -- in addition to is_collective=True below.
                # Every other consumed parameter keeps today's only
                # behavior, InputRole.TRIGGERING.
                input_role=(
                    InputRole.SAMPLED
                    if (
                        parameter_name in parsed_signature.sampled_parameter_names
                        or parameter_name
                        in parsed_signature.collective_parameter_names
                    )
                    else InputRole.TRIGGERING
                ),
                is_collective=(
                    parameter_name in parsed_signature.collective_parameter_names
                ),
            )
            for parameter_name, parameter_type in parsed_signature.consumed_parameters
        )

        produced_artifact = ArtifactDescriptor(
            domain_type=parsed_signature.produced_type,
            role=ArtifactRole.PRODUCED,
            name=self._PRODUCED_NAME,
        )

        context: NodeContextDescriptor | None = None
        if parsed_signature.context_parameter_name is not None:
            assert parsed_signature.context_memory_type is not None
            assert parsed_signature.context_output_type is not None
            context = NodeContextDescriptor(
                parameter_name=parsed_signature.context_parameter_name,
                memory_type=parsed_signature.context_memory_type,
                output_type=parsed_signature.context_output_type,
            )

        return DomainNodeDescription(
            function=self._function,
            consumed_artifacts=consumed_artifacts,
            produced_artifact=produced_artifact,
            context=context,
        )

    def build_definition(self) -> DomainNodeDefinition:
        return DomainNodeDefinition(description=self.build())
