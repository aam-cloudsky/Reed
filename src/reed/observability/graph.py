"""
`reed graph <execution_id>` (Milestone O6, Slice O6d).

Reconstructs one Execution's artifact-dependency graph directly from `provenance.csv`
(Milestone O4), per design record Section 8's round-4 addition: because `provenance.csv` is
a normalized `generated`/`used` event log, a group-by on
`(artifact_id, artifact_version, instance_id)` (the `instance_id` dimension added at Slice
MI-J, docs/refactor/multi_instance_execution_plan.md, Risk R5 -- two different artifact
instances each start their own version sequence at 1, so grouping on
`(artifact_id, artifact_version)` alone would silently collide two distinct instances' first
commits of the same type into one graph node)
gives the producer and every consumer of one artifact version, which is exactly the shape

    NodeA --generated--> ArtifactX <--used-- {NodeB, NodeC}

Two renderings are provided, per the harness row's own menu of options (terminal
tree/graph, or a small self-contained page):

    - `build_provenance_graph(run_dir)` -- the reconstructed graph itself, as a plain data
      structure (`{(artifact_id, artifact_version): ProvenanceGraphNode}`), independent of
      any rendering choice.
    - `render_provenance_tree(run_dir)` -- a Rich `Tree`, reusing the same rendering family
      as the O5b terminal renderer.
    - `render_provenance_dot(run_dir)` -- a standalone Graphviz DOT string, openable with
      any DOT renderer with no Reed-specific tooling and no server (the "small
      self-contained page" option, in text form rather than embedded HTML/JS, since DOT is
      already a plain-text, dependency-free format a person can render themselves).

This is explicitly the nice-to-have consumer Section 8 describes it as, not a requirement
with a committed rendering-technology choice -- both renderings are thin, and either can be
swapped or extended without changing `build_provenance_graph(...)`'s data shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.markup import escape
from rich.tree import Tree

from reed.observability.replay import load_provenance

# Slice MI-J: the same reserved singleton-instance string
# `NodeExecutionIdentity`/`ProvenanceEvent` default `instance_id` to
# (`reed.observability.identity`'s own docstring). Hardcoded here rather
# than imported from `reed.execution.instance_key`, matching that
# module's own deliberately minimal-import precedent -- this module
# already has no dependency on Reed's execution-state internals and this
# slice does not introduce one.
_SINGLETON_INSTANCE_ID = "<InstanceKey.singleton>"


@dataclass
class ProvenanceGraphNode:
    """One artifact version's producer and consumers, per Section 8's group-by."""

    artifact_id: str
    artifact_version: str
    instance_id: str = _SINGLETON_INSTANCE_ID
    producer_node_id: str | None = None
    consumer_node_ids: list[str] = field(default_factory=list)


def build_provenance_graph(
    run_dir: Path,
) -> dict[tuple[str, str, str], ProvenanceGraphNode]:
    """
    Group `<run_dir>/provenance.csv`'s rows by
    `(artifact_id, artifact_version, instance_id)`, producing one
    `ProvenanceGraphNode` per artifact version *and instance* -- its
    `"generated"` row's `node_id` is the producer, its `"used"` rows'
    `node_id`s are the consumers (Section 8's round-4 addition; the
    `instance_id` dimension added at Slice MI-J, this module's own
    docstring above).

    `row.get("instance_id", ...)` tolerates a `provenance.csv` written
    before Slice MI-J's schema bump (no `instance_id` column at all),
    treating every such row as the singleton instance -- the only
    instance that could have existed before this slice.
    """
    graph: dict[tuple[str, str, str], ProvenanceGraphNode] = {}

    for row in load_provenance(run_dir):
        instance_id = row.get("instance_id") or _SINGLETON_INSTANCE_ID
        key = (row["artifact_id"], row["artifact_version"], instance_id)
        node = graph.setdefault(
            key,
            ProvenanceGraphNode(
                artifact_id=row["artifact_id"],
                artifact_version=row["artifact_version"],
                instance_id=instance_id,
            ),
        )
        if row["event_type"] == "generated":
            node.producer_node_id = row["node_id"]
        elif row["event_type"] == "used":
            node.consumer_node_ids.append(row["node_id"])

    return graph


def render_provenance_tree(run_dir: Path) -> Tree:
    """
    Render `build_provenance_graph(run_dir)` as a Rich `Tree`: one root branch
    per artifact version, showing its producer and each consumer as children.

    A branch's label shows `[instance=<instance_id>]` only when
    `instance_id` is not the singleton default (Slice MI-J) -- a
    single-instance-only flow's rendered output is therefore
    byte-for-byte unaffected by this slice.

    Every label is passed through `rich.markup.escape(...)` (found
    missing by the example in examples/multi_instance_fleet_example.py,
    post-MI-J review): Rich's `Tree`/`Console` interpret `[...]` in a
    label as markup syntax, not literal text, so an un-escaped
    `[instance='N-ALPHA']` suffix was silently swallowed -- parsed as an
    unrecognized markup tag and dropped -- rather than displayed. This
    was never caught by MI-J's own tests because none of them rendered
    a TREE for a genuinely multi-instance flow; only the singleton-only
    case (where the suffix is empty and this never triggers) and the
    graph's plain data structure (`build_provenance_graph`, which never
    touches Rich at all) were exercised.
    """
    tree = Tree(f"Reed Provenance -- {run_dir.name}")
    for (artifact_id, artifact_version, instance_id), node in build_provenance_graph(
        run_dir
    ).items():
        suffix = (
            f" [instance={instance_id}]"
            if instance_id != _SINGLETON_INSTANCE_ID
            else ""
        )
        branch = tree.add(escape(f"{artifact_id} v{artifact_version}{suffix}"))
        producer_label = node.producer_node_id or "(no generated event recorded)"
        branch.add(escape(f"generated by {producer_label}"))
        if not node.consumer_node_ids:
            branch.add("(no consumers recorded)")
        else:
            for consumer_node_id in node.consumer_node_ids:
                branch.add(escape(f"used by {consumer_node_id}"))
    return tree


def render_provenance_dot(run_dir: Path) -> str:
    """
    Render `build_provenance_graph(run_dir)` as a standalone Graphviz DOT
    string: one edge `producer -> artifact` per artifact version, and one
    edge `artifact -> consumer` per consumer -- openable with any DOT
    renderer, no Reed-specific tooling, no server.

    An artifact node's own label shows `[instance=<instance_id>]` only
    when `instance_id` is not the singleton default (Slice MI-J), for the
    same byte-for-byte-unaffected reason as `render_provenance_tree`.
    """
    lines = ["digraph reed_provenance {"]
    for (artifact_id, artifact_version, instance_id), node in build_provenance_graph(
        run_dir
    ).items():
        suffix = (
            f" [instance={instance_id}]"
            if instance_id != _SINGLETON_INSTANCE_ID
            else ""
        )
        artifact_label = f'"{artifact_id} v{artifact_version}{suffix}"'
        if node.producer_node_id is not None:
            lines.append(f'  "{node.producer_node_id}" -> {artifact_label};')
        for consumer_node_id in node.consumer_node_ids:
            lines.append(f'  {artifact_label} -> "{consumer_node_id}";')
    lines.append("}")
    return "\n".join(lines)
