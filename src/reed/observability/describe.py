"""
`reed describe` (Milestone O6, Slice O6b).

Introspects a Flow's declared Instruments -- **no execution required** (design record
Section 8/harness row O6b): this reads `Flow.flow_nodes`/`FlowNode.instruments` directly
(Milestone O2's declared-mode `flow.add(node, instruments=[...])`), or the
`instruments.json` manifest a past `Run` already wrote (Milestone O3, Slice O3e), never a
live `Run` or `ExecutionTrace`. A Node's declared Instruments are part of its own
definition, not something that only exists once something has run.

Lazy-mode Recordings (Slice O2e, `kind=None`) are, by construction, not declared anywhere
ahead of time (docs/observability_goals.md Section 2.1) -- there is nothing for `describe`
to introspect about them without an actual `recordings.csv` to read (that is `reed query`,
Slice O6c's job, not `describe`'s).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rich.table import Table

if TYPE_CHECKING:
    from reed.composition.flow.flow_composition import Flow


# Milestone O7, Slice O7f: a blank instrument cell for a Node with no
# `instruments=[...]` declared reads as "declared nothing, no signal at
# all" -- but that Node is exactly the one still eligible for lazy-mode
# `ctx.record(name, value)` calls (declared mode requires a non-empty
# `instruments=[...]`; an empty one is what makes lazy mode active at all,
# docs/observability_goals.md Section 2.3). Reed cannot know statically
# whether such a Node actually calls `ctx.record(...)` at runtime -- that
# is exactly the distinction to preserve: "may emit lazy Recordings,
# unknown before execution" is not the same claim as "this Node has no
# Instruments," and describe_flow must not conflate the two.
LAZY_CAPABLE_LABEL = "<lazy -- may record, unknown before execution>"


def describe_flow(flow: "Flow") -> Table:
    """
    Build a Rich `Table` of every `FlowNode` in `flow` and its declared
    Instruments (name/kind/unit/description), read directly off `Flow.
    flow_nodes`/`FlowNode.instruments` -- no `Run`, no execution.

    A Node declared with no `instruments=[...]` appears with
    `LAZY_CAPABLE_LABEL` in its instrument column (Slice O7f) rather than
    a blank cell -- it is statically eligible for lazy-mode
    `ctx.record(...)` calls, which is different information from "this
    Node has no Instruments at all," even though describe_flow cannot
    know whether it actually will record anything until it runs.
    """
    table = Table(title=f"Reed Flow -- {flow.flow_id}")
    table.add_column("node_id")
    table.add_column("instrument")
    table.add_column("kind")
    table.add_column("unit")

    for flow_node in flow.flow_nodes:
        if not flow_node.instruments:
            table.add_row(flow_node.node_id, LAZY_CAPABLE_LABEL, "", "")
            continue
        for instrument in flow_node.instruments:
            table.add_row(
                flow_node.node_id, instrument.name, instrument.kind, instrument.unit
            )

    return table


def describe_instruments_manifest(path: Path) -> Table:
    """
    Same report as `describe_flow(...)`, sourced from a past Run's
    `<storage_root>/flows/<flow_id>/instruments.json` (Milestone O3, Slice
    O3e) instead of a live `Flow` object -- for introspecting a Flow whose
    source code is not available to import right now, only its manifest.
    """
    content = json.loads(path.read_text())
    table = Table(title=f"Reed Flow -- {content['flow_id']}")
    table.add_column("node_id")
    table.add_column("instrument")
    table.add_column("kind")
    table.add_column("unit")

    for node_id, node_data in content["nodes"].items():
        instruments = node_data["instruments"]
        if not instruments:
            table.add_row(node_id, LAZY_CAPABLE_LABEL, "", "")
            continue
        for instrument in instruments:
            table.add_row(node_id, instrument["name"], instrument["kind"], instrument["unit"])

    return table
