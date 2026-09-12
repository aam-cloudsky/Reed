"""
TriggerPolicy.

`TriggerPolicy` decides whether a `FlowNode` becomes eligible to execute
after one or more of its consumed artifact types receives a new committed
value (`Run.publish`'s propagation cascade, `Run._is_eligible_to_fire`).

    TriggerPolicy != on_output (docs/architectural_invariants.md #20):
    a `TriggerPolicy` decides *whether* a Node fires; `on_output`
    observes a Node's committed result strictly after it has already
    fired successfully. Neither one is a scheduler, retry policy, or
    routing mechanism.

This is Reed's only execution-eligibility policy. The previous
`PropagationPolicy` enum and its `Node`/`NodeDefinition`-based
execution-eligibility path (superseded by this enum and by
`Run`/`FlowNode`) have been retired along with the rest of the legacy
decorator/Parcel programming model; see docs/refactor_state.md for that
removal's history.
"""

from __future__ import annotations

from enum import Enum, auto


class TriggerPolicy(Enum):
    """Decides whether a FlowNode becomes eligible to execute after input
    artifact changes."""

    ANY_INPUT_CHANGED = auto()
    ALL_INPUTS_CHANGED = auto()
    MANUAL = auto()
