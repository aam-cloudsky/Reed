"""
NodeExecutionIdentity (Milestone O1, Slice O1f).

A small, immutable, read-only bundle of Reed's own observability identity
fields, attached to a `NodeContext` snapshot at the moment a Node actually
fires (`reed.execution.session.Session._begin_node_execution`).

Scope (docs/refactor/observability_goals.md Section 3; docs/refactor/observability_design.md
Section 16.3, Section 17.1's resolution in Section 18):

    execution_id       -- one Session instance (uuid4, minted in Session.__init__).
    flow_id            -- one logical Flow definition, deterministic and
                           stable across separate process runs of the same
                           Flow composition (Flow.flow_id).
    node_id            -- one FlowNode within a Flow, deterministic and
                           stable across separate process runs
                           (FlowNode.node_id).
    node_execution_id  -- one firing of one Node within one Session (uuid4,
                           minted per firing).
    execution_seq      -- a monotonic counter, scoped to one execution_id,
                           incremented once per node_execution_id minted.
                           A DETERMINISTIC OBSERVATION ORDER, never a
                           causality claim (docs/refactor/observability_design.md
                           Section 13.1; docs/refactor/observability_invariants.md
                           #7-9).
    instance_id         -- Slice MI-J (docs/refactor/
                           multi_instance_execution_plan.md, Risk R5):
                           the resolved `InstanceKey` of the artifact
                           instance this firing (or this "used"
                           dependency) is scoped to, as a plain string
                           (`Session._instance_identifier`). Defaults to
                           `"<InstanceKey.singleton>"` -- deliberately the
                           exact `repr()` of `InstanceKey.singleton()`'s
                           own private sentinel object
                           (`reed.execution.instance_key.
                           _InstanceKeySingletonSentinel.__repr__`),
                           confirmed by reading that module, without this
                           deliberately minimal-import module importing
                           `InstanceKey` itself. Every pre-multi-instance
                           firing resolves to this same default, so
                           existing single-instance flows' observability
                           output is unaffected by this field's addition.

This bundle deliberately holds no reference back to `Session`, `Flow`,
`NodeSession`, or anything else internal to Reed's execution
infrastructure -- only these six plain values (architectural_invariants.md
#26; docs/refactor/observability_non_goals.md's "NodeContext Scope" constraint,
carried over from `docs/history/node_context_decision.md`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NodeExecutionIdentity:
    """Read-only identity bundle attached to one Node firing's `NodeContext`."""

    execution_id: str
    flow_id: str
    node_id: str
    node_execution_id: str
    execution_seq: int
    instance_id: str = "<InstanceKey.singleton>"
