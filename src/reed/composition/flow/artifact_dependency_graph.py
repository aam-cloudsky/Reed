"""
ArtifactDependencyGraph (Slice 1D, Priority 8).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1D; docs/parcel_boundary_decision.md, "Unique Producer Responsibility" and
"No Self-Flow"; docs/architecture.md, "Dependency Management"):

    ArtifactDependencyGraph
        producers by artifact type
        consumers by artifact type
        upstream FlowNodes
        downstream FlowNodes

This is `DependencyRegistry` (`reed.synchronization.validity.dependency_registry`)
migrated to `FlowNode`/domain-artifact-type vocabulary, per Priority 8's
own recommended target name. It preserves the unique-producer rule the
old registry already enforced, and adds self-flow validation at
registration time -- a second, composition-level enforcement of the same
invariant Slice 1A's `DomainNodeSignatureParser` already enforces at
signature-parsing time (architectural_invariants.md #11): a `FlowNode`
built by hand (bypassing the parser) would otherwise slip through.

This is additive alongside the existing `DependencyRegistry`
(`dependency_registry.py`), which is NOT modified and remains the
current, regression-protected path (`tests/test_current_regression_artifacts_repository.py::test_dependency_registry_*`).
The two are not merged in this slice -- see the Rename Rule in
`docs/refactor_agent_protocol.md`: "First make the boundary real. Then
rename the boundary." The old registry is keyed by an arbitrary
`module_type` and `Parcel` subclass and may allow a module to produce
multiple Parcel types; `ArtifactDependencyGraph` is keyed by `FlowNode`
(Slice 1C) and domain artifact type, and a `FlowNode` produces exactly
one domain artifact type (`FlowNode.produced_artifact`, singular -- see
Slice 1B/1C), so its shape is intentionally not a 1:1 mirror of the old
API.

Explicitly out of scope for this slice:

    - `PropagationPolicy` -> `TriggerPolicy` migration (Priority 10,
      Slice 1E) is unrelated and not touched.
    - As of Slice 1F, `Flow.add(...)` calls `register(...)` on this
      graph for every added node -- completing Priority 8's
      recommended work item 5 ("move validation earlier into Flow
      composition"). This file's own class is unchanged by that
      wiring; it remains a standalone, directly usable class.
"""

from __future__ import annotations

from collections import defaultdict

from reed.composition.flow.flow_node import FlowNode


class DuplicateArtifactProducerError(RuntimeError):
    """
    Raised when a second `FlowNode` attempts to produce a domain artifact
    type that already has a different registered producer.
    """

    def __init__(
        self,
        *,
        domain_type: type,
        current_producer: FlowNode,
        new_producer: FlowNode,
    ) -> None:
        super().__init__(
            "DuplicateArtifactProducerError\n\n"
            f"Artifact type:\n    {domain_type.__name__}\n\n"
            f"Current producer:\n    {current_producer.definition.name}\n\n"
            f"New producer:\n    {new_producer.definition.name}\n\n"
            "Only one producer per domain artifact type is allowed "
            "within one Flow."
        )


class SelfFlowError(RuntimeError):
    """
    Raised when a `FlowNode` consumes the same domain artifact type it
    produces (architectural_invariants.md #11).
    """

    def __init__(
        self,
        *,
        flow_node: FlowNode,
        domain_type: type,
    ) -> None:
        super().__init__(
            "SelfFlowError\n\n"
            f"Node:\n    {flow_node.definition.name}\n\n"
            f"Artifact type:\n    {domain_type.__name__}\n\n"
            "A Node cannot consume and produce the same domain artifact "
            "type."
        )


class ArtifactDependencyGraph:
    """
    Declarative graph of `FlowNode` participations keyed by domain
    artifact type.

    This class does NOT:
    - execute nodes;
    - resolve execution order;
    - observe status/dirty-flag changes.

    It only knows:
    - which `FlowNode`s exist;
    - which domain artifact types they consume/produce;
    - which `FlowNode`s depend on which.
    """

    def __init__(self) -> None:
        # domain artifact type -> the one FlowNode that produces it
        self._producer_by_type: dict[type, FlowNode] = {}

        # domain artifact type -> FlowNodes that consume it
        self._consumers_by_type: dict[type, set[FlowNode]] = defaultdict(set)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, flow_node: FlowNode) -> None:
        """
        Registers one `FlowNode`'s consumed/produced domain artifact
        types.

        Raises:
            SelfFlowError:
                If `flow_node` consumes the same domain artifact type it
                produces.
            DuplicateArtifactProducerError:
                If a different `FlowNode` already produces the same
                domain artifact type.
        """

        produced_type = flow_node.produced_artifact.domain_type
        consumed_types = {
            artifact.domain_type for artifact in flow_node.consumed_artifacts
        }

        if produced_type in consumed_types:
            raise SelfFlowError(flow_node=flow_node, domain_type=produced_type)

        existing_producer = self._producer_by_type.get(produced_type)

        if existing_producer is not None and existing_producer is not flow_node:
            raise DuplicateArtifactProducerError(
                domain_type=produced_type,
                current_producer=existing_producer,
                new_producer=flow_node,
            )

        self._producer_by_type[produced_type] = flow_node

        for consumed_type in consumed_types:
            self._consumers_by_type[consumed_type].add(flow_node)

    def unregister(self, flow_node: FlowNode) -> None:
        produced_type = flow_node.produced_artifact.domain_type

        if self._producer_by_type.get(produced_type) is flow_node:
            del self._producer_by_type[produced_type]

        for artifact in flow_node.consumed_artifacts:
            consumers = self._consumers_by_type.get(artifact.domain_type)

            if consumers is None:
                continue

            consumers.discard(flow_node)

            if not consumers:
                del self._consumers_by_type[artifact.domain_type]

    # ------------------------------------------------------------------
    # Queries (structural)
    # ------------------------------------------------------------------

    def producer_of(self, domain_type: type) -> FlowNode | None:
        return self._producer_by_type.get(domain_type)

    def consumers_of(self, domain_type: type) -> frozenset[FlowNode]:
        return frozenset(self._consumers_by_type.get(domain_type, set()))

    # ------------------------------------------------------------------
    # DAG Edges (FlowNode -> FlowNode)
    # ------------------------------------------------------------------

    def upstream_flow_nodes(self, flow_node: FlowNode) -> frozenset[FlowNode]:
        """
        FlowNodes that must run BEFORE this FlowNode.
        """
        upstream: set[FlowNode] = set()

        for artifact in flow_node.consumed_artifacts:
            producer = self.producer_of(artifact.domain_type)
            if producer is not None:
                upstream.add(producer)

        return frozenset(upstream)

    def downstream_flow_nodes(self, flow_node: FlowNode) -> frozenset[FlowNode]:
        """
        FlowNodes that depend on this FlowNode.
        """
        produced_type = flow_node.produced_artifact.domain_type
        return self.consumers_of(produced_type)
