"""
TriggerPolicy (Slice 1E, Priority 10).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1E; docs/flow_composition_implementation_basis.md, "TriggerPolicy";
docs/architectural_invariants.md #18-20; docs/non-goals.md, "TriggerPolicy
Scope"):

    TriggerPolicy
        renames the old PropagationPolicy vocabulary
        decides whether a FlowNode becomes eligible to execute
        after input artifact changes
        is not a scheduler, callback system, retry policy, or
        routing mechanism (non-goals.md)
        TriggerPolicy != on_output (architectural_invariants.md #20)

This module also updates `FlowNode.trigger_policy` (Slice 1C) to be typed
against this enum instead of the old `PropagationPolicy`. Per
docs/refactor_priority_order.md, "FlowNode / DependencyRegistry ordering
(resolved)": `FlowNode.trigger_policy` already existed (Slice 1C); this
slice only renames the enum it is typed against and finishes relocating
its ownership onto `FlowNode`. This is not a forward dependency -- nothing
here references a type that doesn't exist yet.

Explicitly out of scope for this slice:

    - No change to the old `PropagationPolicy` enum
      (`reed.composition.node.propagation_policy`), `NodeDefinition`, or
      `Node`. That Parcel/decorator-based path, including its
      execution-eligibility `match` statement over `PropagationPolicy`,
      remains fully intact and regression-protected.
    - No execution logic reads `FlowNode.trigger_policy` or this enum yet
      (Priority 10 recommended-work item 4, "later update execution logic
      to read from FlowNode", is deferred -- that belongs with the
      `Run`/`NodeRuntime` execution boundary in Milestone 2).
    - As of Slice 1F, `Flow.add(...)` accepts `trigger_policy` as a
      keyword-only argument and stores it on the returned `FlowNode`
      as composition metadata only -- it is still never read or
      evaluated by anything.
    - No `on_output` dispatch semantics (Milestone 2, Slice 2F).
    - `TriggerPolicy` is exposed at the `reed` package top level as of
      Slice 1F (`reed.TriggerPolicy`), bundled with `Flow.add(...)`'s
      introduction as anticipated here.

Value naming note: one example in
docs/flow_composition_implementation_basis.md uses
`TriggerPolicy.ON_ANY_INPUT_CHANGED`, which is a documented typo (see
docs/reed_refactor_harness.md's Known Issues / doc-consistency note). The
canonical value is `ANY_INPUT_CHANGED`, matching
docs/refactor_priority_order.md's Priority 10 target block and
tests/test_target_architecture_contract.py's actual usage.
"""

from __future__ import annotations

from enum import Enum, auto

from reed.composition.node.propagation_policy import PropagationPolicy


class TriggerPolicy(Enum):
    """Decides whether a FlowNode becomes eligible to execute after input
    artifact changes. See module docstring for the exact Slice 1E scope."""

    ANY_INPUT_CHANGED = auto()
    ALL_INPUTS_CHANGED = auto()
    MANUAL = auto()


_PROPAGATION_POLICY_TO_TRIGGER_POLICY: dict[PropagationPolicy, TriggerPolicy] = {
    PropagationPolicy.ANY_DEPENDENCY_CHANGED: TriggerPolicy.ANY_INPUT_CHANGED,
    PropagationPolicy.ALL_DEPENDENCIES_CHANGED: TriggerPolicy.ALL_INPUTS_CHANGED,
    PropagationPolicy.MANUAL: TriggerPolicy.MANUAL,
}


def from_propagation_policy(policy: PropagationPolicy) -> TriggerPolicy:
    """Map an old `PropagationPolicy` value to its `TriggerPolicy`
    equivalent (Priority 10 recommended-work item 2: "map old values to
    new values").

    This is a pure value mapping. It is not called from any execution
    path in this slice -- no compatibility bridge into `Node`'s
    execution-eligibility logic is wired here; that remains Priority 10
    recommended-work item 4, explicitly deferred.
    """

    return _PROPAGATION_POLICY_TO_TRIGGER_POLICY[policy]
