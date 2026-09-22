"""
Milestone O6, Slice O6d -- `reed graph <execution_id>`: reconstruct the
artifact-dependency graph from provenance.csv (design record §28).
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class Verdict:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_fan_out_flow():
    from reed import Flow

    def stage_one(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def consumer_b(estimate: Estimate) -> Verdict:
        return Verdict(estimate.value + 1)

    flow = Flow()
    flow.add(stage_one)
    flow.add(consumer_b)
    return flow, stage_one, consumer_b


def test_build_provenance_graph_groups_by_artifact_version(tmp_path):
    from reed.observability.graph import build_provenance_graph

    flow, stage_one, consumer_b = _make_fan_out_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    graph = build_provenance_graph(run_dir)

    estimate_keys = [key for key in graph if key[0].endswith("Estimate")]
    assert len(estimate_keys) == 1
    node = graph[estimate_keys[0]]
    assert node.producer_node_id is not None
    assert node.producer_node_id.endswith("stage_one")


def test_used_edge_appears_once_producer_and_consumer_both_fire(tmp_path):
    from reed.observability.graph import build_provenance_graph

    flow, stage_one, consumer_b = _make_fan_out_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()
    session.feed(Estimate(5))
    session.push()

    run_dir = root / "runs" / session.execution_id
    graph = build_provenance_graph(run_dir)

    estimate_keys = [key for key in graph if key[0].endswith("Estimate")]
    node = graph[estimate_keys[0]]
    assert any(c.endswith("consumer_b") for c in node.consumer_node_ids)


def test_render_provenance_tree_contains_artifact_and_producer(tmp_path):
    from reed.observability.graph import render_provenance_tree

    flow, stage_one, consumer_b = _make_fan_out_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    tree = render_provenance_tree(run_dir)

    from rich.console import Console

    console = Console(record=True, width=200)
    console.print(tree)
    output = console.export_text()

    assert "Estimate" in output
    assert "stage_one" in output


def test_render_provenance_dot_produces_valid_digraph_text(tmp_path):
    from reed.observability.graph import render_provenance_dot

    flow, stage_one, consumer_b = _make_fan_out_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
    dot = render_provenance_dot(run_dir)

    assert dot.startswith("digraph reed_provenance {")
    assert dot.endswith("}")
    assert "stage_one" in dot
    assert "Estimate" in dot
