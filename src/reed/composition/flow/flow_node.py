"""
FlowNode (Slice 1C, Priority 9; `trigger_policy` typing updated in Slice
1E, Priority 10).

Scope for this slice (docs/history/refactor_priority_order.md, Milestone 1, Slice
1C; docs/history/flow_composition_implementation_basis.md, "FlowNode"):

    FlowNode
        flow-local node participation
        owns trigger_policy
        owns on_output
        points to NodeDefinition
        exposes produced and consumed artifact descriptors

`trigger_policy` is typed against `TriggerPolicy`
(`reed.composition.flow.trigger_policy`, Slice 1E). It was originally
typed against the old `PropagationPolicy` enum in Slice 1C, deliberately,
because `TriggerPolicy` did not exist yet; Slice 1E introduced
`TriggerPolicy` and finished relocating this field's type onto it. See
docs/history/refactor_priority_order.md, "FlowNode / DependencyRegistry ordering
(resolved)": this was not a forward dependency in 1C, and the type update
here is exactly the relocation that note anticipated for 1E -- nothing in
1C referenced a type that didn't exist yet, and nothing here changes the
field's ownership (it lived on FlowNode since 1C).

Explicitly out of scope (this slice and 1E):

    - As of Slice 1F, `Flow.add(...)`
      (`reed.composition.flow.flow_composition.Flow`, exported as
      `reed.Flow`) constructs and returns `FlowNode` instances; this
      file's own class is unchanged by that wiring. `FlowNode` remains
      directly constructible on its own, as it was in this slice.
      Today's other `Flow` (`reed.composition.flow.flow`) is the old
      decorator-bound compatibility class and is still unrelated.
    - `DependencyRegistry` migration (Priority 8, Slice 1D) is not
      implemented here; a `FlowNode` does not register itself anywhere.
    - No execution logic reads `trigger_policy` yet (Priority 10
      recommended-work item 4, "later update execution logic to read
      from FlowNode") -- the old `Node`'s execution-eligibility `match`
      statement over `PropagationPolicy` is untouched and still what
      actually runs today; this field is not yet consulted by anything.
    - `on_output` has no dispatch semantics yet (commit-then-callback
      ordering, async support, failure isolation) -- that is Milestone 2,
      Slice 2F. Here it is a plain, optional, stored callable.
    - No separate flow-local "identity" field (a distinct id/handle) is
      introduced. Per `docs/history/non-goals.md`, "Multiple Registrations of the
      Same Node Definition", node participation identity semantics
      (whether/how the same NodeDefinition can participate more than
      once in one Flow) are explicitly undecided and out of scope. The
      `FlowNode` instance itself is the flow-local reference
      (docs/refactor/architectural_decision.md, "Flow-Local Node Reference") --
      no additional identity field is needed at this slice.
    - This class holds the domain-typed `DomainNodeDefinition` (Slice
      1B), not the old Parcel-centric `NodeDefinition`
      (`reed.composition.node.node_definition`); the two are unrelated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from reed.composition.node.artifact_descriptor import ArtifactDescriptor
from reed.composition.node.domain_node_description import (
    DomainNodeDefinition,
    NodeContextDescriptor,
)
from reed.composition.flow.trigger_policy import TriggerPolicy


@dataclass(frozen=True)
class FlowNode:
    """
    One `DomainNodeDefinition` participating in one Flow's composition.

    See module docstring for the exact Slice 1C scope.
    """

    definition: DomainNodeDefinition
    trigger_policy: TriggerPolicy = TriggerPolicy.ALL_INPUTS_CHANGED
    on_output: Callable[[Any], object] | None = None
    # Milestone O2 originally added a declared-Instruments field here
    # (`instruments: tuple[Instrument, ...] = ()`, populated by
    # `flow.add(node, instruments=[...])`). Milestone O7, Slice O7i
    # removed it: Instruments are now typed Instrument Definitions
    # (`reed.observability.instrument.Instrument` subclasses) discovered
    # dynamically the first time a Node calls `ctx.record(SomeInstrument,
    # value)`, never prospectively declared by the Flow -- see that
    # module's docstring. `FlowNode` no longer carries any
    # Instrument-related field at all.

    @property
    def consumed_artifacts(self) -> tuple[ArtifactDescriptor, ...]:
        return self.definition.description.consumed_artifacts

    @property
    def produced_artifact(self) -> ArtifactDescriptor:
        return self.definition.description.produced_artifact

    @property
    def context(self) -> NodeContextDescriptor | None:
        return self.definition.description.context

    @property
    def node_id(self) -> str:
        """
        This `FlowNode`'s stable observability identity (Milestone O1,
        Slice O1c; docs/refactor/observability_design.md Section 18 -- `flow_id`/
        `node_id` cross-session stability).

        Deterministically derived from the wrapped function's module and
        qualified name (`f"{function.__module__}.{function.__qualname__}"`),
        NOT from `id(self)` or any other per-process runtime value -- this
        is what makes it reproducible across separate process runs of the
        same source code, with no user-supplied identifier and no `name=`
        parameter on `Flow.add(...)` (docs/refactor/observability_non_goals.md
        Section 8).

        Explicitly NOT required to be unique, in this Flow or across
        Flows (docs/refactor/observability_design.md Section 16.5, retracting the
        uniqueness-validation proposal in Section 12.3): identity/
        correlation always uses `node_id` together with `flow_id`
        (`instrument_id = (flow_id, node_id, name)`), so a `node_id`
        collision alone causes no correlation ambiguity. The only
        invariant that causes composition failure remains the existing
        one -- within a Flow, each Artifact type has exactly one
        producer.
        """
        function = self.definition.function
        return f"{function.__module__}.{function.__qualname__}"

    @property
    def node_name(self) -> str:
        """
        This `FlowNode`'s display label (Milestone O1, Slice O1c) --
        presentation metadata only, never identity
        (docs/refactor/observability_invariants.md #5). Defaults to the wrapped
        function's `__name__`; not required to be unique. Use `node_id`
        for correlation, never this.
        """
        return self.definition.function.__name__
