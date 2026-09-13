"""
`reed describe` (Milestone O6, Slice O6b; redesigned at Milestone O7,
Slice O7i for dynamically-discovered Instruments).

## O7i redesign

Prior to O7i, `describe_flow(flow)` introspected a Flow's *prospectively
declared* Instruments (`flow.add(node, instruments=[...])`) with no
execution required at all -- an Instrument's existence was static,
composition-time information. Milestone O7, Slice O7i removed prospective
declaration entirely: an Instrument (a typed `Instrument` subclass,
`reed.observability.instrument`) is now discovered dynamically, the first
time a Node actually calls `ctx.record(SomeInstrument, value)` during a
real `Run`. `describe_flow(flow)` therefore **cannot** claim any static
Instrument knowledge anymore -- there is no `FlowNode.instruments` field
left to read, and Reed deliberately does not recover this information via
`AST` inspection of a Node's body (docs/observability_non_goals.md's
general "no reflection-based magic" posture; explicitly reiterated by the
task that authorized this redesign). `describe_flow` still enumerates
every Node in the Flow (so it remains useful for "what Nodes exist," the
one thing genuinely knowable with no execution), but its Instrument
column now honestly reports that discovery is runtime-only, for every
Node uniformly -- not a per-Node "declared vs. lazy" distinction, since
that distinction no longer exists.

`describe_instruments_manifest(path)` is now the primary way to actually
see an Instrument's kind/unit/description: it reads
`<storage_root>/flows/<flow_id>/instruments.json`, which
`Run.record_discovered_instruments(...)` merges into as real executions
discover real bindings (see `storage.py`'s `merge_discovered_instruments`)
-- an accurate, if necessarily retrospective, picture of every
(node_id, Instrument) binding any past `Run` of this `flow_id` has
actually exercised.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rich.table import Table

if TYPE_CHECKING:
    from reed.composition.flow.flow_composition import Flow


# Milestone O7, Slice O7f (retained, generalized at Slice O7i): a Node's
# Instrument column has no static information to show -- describe_flow
# cannot know, without executing the Flow, which Instrument(s) (if any) a
# Node's body will call `ctx.record(...)` with. This label makes that
# honest rather than rendering a blank cell (which would read as "this
# Node definitely has no Instruments," a claim describe_flow cannot make).
DISCOVERED_AT_RUNTIME_LABEL = "<discovered at runtime -- see reed describe --manifest>"

# Slice O7f's original name, kept as an alias: Slice O7i's redesign
# generalized "may be lazy" (an O2e-era, per-Node distinction) into
# "every Instrument is runtime-discovered" (an O7i, Flow-wide fact), but
# existing callers/tests referencing the old name still get a real label.
LAZY_CAPABLE_LABEL = DISCOVERED_AT_RUNTIME_LABEL


def describe_flow(flow: "Flow") -> Table:
    """
    Build a Rich `Table` of every `FlowNode` in `flow` -- no `Run`, no
    execution. Since Milestone O7, Slice O7i, Instruments are discovered
    dynamically rather than prospectively declared, so every row's
    Instrument column reads `DISCOVERED_AT_RUNTIME_LABEL`: this method
    can state which Nodes exist, but not which Instruments (if any) they
    will record. See `describe_instruments_manifest(...)` for actually
    observed Instrument bindings from a past Run.
    """
    table = Table(title=f"Reed Flow -- {flow.flow_id}")
    table.add_column("node_id")
    table.add_column("instrument")
    table.add_column("kind")
    table.add_column("unit")

    for flow_node in flow.flow_nodes:
        table.add_row(flow_node.node_id, DISCOVERED_AT_RUNTIME_LABEL, "", "")

    return table


def describe_instruments_manifest(path: Path) -> Table:
    """
    Report every Instrument binding actually *discovered* across past
    Runs of one Flow, read from `<storage_root>/flows/<flow_id>/
    instruments.json` (Milestone O3, Slice O3e; merged dynamically since
    Milestone O7, Slice O7i -- see `storage.merge_discovered_instruments`).

    Unlike `describe_flow(...)`, this can genuinely report `kind`/`unit`/
    `description`, because it reflects Instrument bindings a real `Run`
    actually observed -- not a static declaration. A Node that has never
    yet called `ctx.record(...)` in any Run of this Flow simply does not
    appear here at all (there is nothing to report for it, and no
    static declaration to fall back on describing).
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
            table.add_row(node_id, DISCOVERED_AT_RUNTIME_LABEL, "", "")
            continue
        for instrument in instruments:
            table.add_row(node_id, instrument["name"], instrument["kind"], instrument["unit"])

    return table
