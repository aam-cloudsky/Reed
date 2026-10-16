"""
Slice MI-J: Observability integration -- per-instance firings and commits
correctly distinguishable in the durable provenance record (R5,
docs/refactor/multi_instance_execution_plan.md, Section 2: "the single
largest-blast-radius risk... the one most likely to look finished while
quietly producing misleading traces").

Two genuine pre-existing bugs, fixed here rather than newly introduced
(see this slice's own SliceContract for the full disclosure):

    1. `Session._emit_used_provenance_events` looked up the committed
       record with no `instance=` argument at all, always reading the
       SINGLETON slot regardless of which instance was actually firing.
    2. `graph.py`'s `build_provenance_graph` grouped rows by
       `(artifact_id, artifact_version)` alone, which silently collided
       two different instances' first-ever commits of the same type
       (each starting its own version sequence at 1, invariant #28)
       into one graph node.

Disclosed, in-scope decisions exercised as passing assertions, not
xfails: a `Collective`-marked consumed descriptor (Slice MI-H) is
skipped entirely by `_emit_used_provenance_events` -- it resolves to
potentially many records across many instances at once, not a single
(artifact, version, instance) triple a "used" event can cleanly
attribute; and a singleton-only flow's provenance/graph/replay output is
byte-for-byte unaffected by this slice's additive `instance_id` field.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console

from reed import Collective, Flow, InstanceKey
from reed.observability.graph import build_provenance_graph, render_provenance_tree
from reed.observability.replay import load_provenance

INSTANCE_A = InstanceKey(key="A")
INSTANCE_B = InstanceKey(key="B")

_SINGLETON_INSTANCE_ID = "<InstanceKey.singleton>"


@dataclass
class AircraftState:
    altitude: float


@dataclass
class DeltaT:
    seconds: float


@dataclass
class Observation:
    altitude: float


@dataclass
class FleetSummary:
    total_altitude: float
    count: int


def _run_dir(root, session):
    return root / "runs" / session.execution_id


def test_generated_event_carries_the_firing_instances_own_id(tmp_path):
    def track(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(track)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    rows = load_provenance(_run_dir(root, session))

    observation_generated = [
        row
        for row in rows
        if row["event_type"] == "generated" and row["artifact_id"].endswith("Observation")
    ]
    assert len(observation_generated) == 2
    assert {row["instance_id"] for row in observation_generated} == {
        repr(INSTANCE_A.key),
        repr(INSTANCE_B.key),
    }


def test_used_event_reports_the_actual_per_instance_dependency_not_the_singleton_default(
    tmp_path,
):
    def track(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(track)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    rows = load_provenance(_run_dir(root, session))

    used_rows = [
        row
        for row in rows
        if row["event_type"] == "used" and row["artifact_id"].endswith("AircraftState")
    ]
    assert len(used_rows) == 2

    instance_ids = {row["instance_id"] for row in used_rows}
    # Before this slice's fix, `_emit_used_provenance_events` always read
    # the singleton slot -- these would either be missing entirely or
    # wrongly report the singleton default here.
    assert instance_ids == {repr(INSTANCE_A.key), repr(INSTANCE_B.key)}
    assert _SINGLETON_INSTANCE_ID not in instance_ids


def test_used_event_falls_back_to_the_singleton_scoped_broadcast_dependency(tmp_path):
    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        return Observation(altitude=state.altitude + dt.seconds)

    flow = Flow()
    flow.add(perception)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    # DeltaT is the broadcast dependency (Slice MI-G): fed once, at
    # singleton scope, never per instance.
    session.feed(DeltaT(seconds=0.5))
    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    rows = load_provenance(_run_dir(root, session))

    delta_t_used = [
        row
        for row in rows
        if row["event_type"] == "used" and row["artifact_id"].endswith("DeltaT")
    ]
    assert len(delta_t_used) == 2
    # Each firing's own instance (A, B) has no A/B-scoped DeltaT record of
    # its own -- the "used" event must fall back to, and report, the
    # singleton-scoped record that actually satisfied the dependency.
    assert all(row["instance_id"] == _SINGLETON_INSTANCE_ID for row in delta_t_used)

    aircraft_used = [
        row
        for row in rows
        if row["event_type"] == "used" and row["artifact_id"].endswith("AircraftState")
    ]
    assert {row["instance_id"] for row in aircraft_used} == {
        repr(INSTANCE_A.key),
        repr(INSTANCE_B.key),
    }


def test_two_instances_first_commits_do_not_collide_in_the_provenance_graph(tmp_path):
    flow = Flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
        }
    )

    graph = build_provenance_graph(_run_dir(root, session))

    aircraft_keys = [key for key in graph if key[0].endswith("AircraftState")]
    # Without the instance_id dimension in the group-by key, both
    # instances' first-ever commit (each independently version 1, per
    # invariant #28) would collide into a single graph node.
    assert len(aircraft_keys) == 2
    assert {key[1] for key in aircraft_keys} == {"1"}
    assert {key[2] for key in aircraft_keys} == {repr(INSTANCE_A.key), repr(INSTANCE_B.key)}


def test_singleton_only_flow_provenance_and_graph_output_is_completely_unaffected(tmp_path):
    def stage_one(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(stage_one)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(AircraftState(altitude=42.0))
    session.push()

    run_dir = _run_dir(root, session)
    graph = build_provenance_graph(run_dir)

    observation_keys = [key for key in graph if key[0].endswith("Observation")]
    assert len(observation_keys) == 1
    assert observation_keys[0][2] == _SINGLETON_INSTANCE_ID

    tree = render_provenance_tree(run_dir)
    console = Console(record=True, width=200)
    console.print(tree)
    output = console.export_text()

    assert "Observation" in output
    assert "stage_one" in output
    # The singleton default must never leak into rendered output as a
    # visible "[instance=...]" suffix.
    assert "[instance=" not in output


def test_collective_dependency_is_skipped_by_used_event_emission(tmp_path):
    def fleet_summary(
        tick: DeltaT,
        states: Collective[AircraftState],
    ) -> FleetSummary:
        altitudes = tuple(s.altitude for s in states)
        return FleetSummary(total_altitude=sum(altitudes), count=len(altitudes))

    flow = Flow()
    flow.add(fleet_summary)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.feed(DeltaT(seconds=1.0))
    session.push()

    rows = load_provenance(_run_dir(root, session))

    aircraft_used = [
        row
        for row in rows
        if row["event_type"] == "used" and row["artifact_id"].endswith("AircraftState")
    ]
    assert aircraft_used == []

    delta_t_used = [
        row
        for row in rows
        if row["event_type"] == "used" and row["artifact_id"].endswith("DeltaT")
    ]
    assert len(delta_t_used) == 1

    summary = session.repository.get_artifact_record(FleetSummary).value
    assert summary.count == 2


def test_feed_instances_generated_event_carries_its_own_instance_id(tmp_path):
    flow = Flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
        }
    )

    rows = load_provenance(_run_dir(root, session))

    aircraft_generated = [
        row
        for row in rows
        if row["event_type"] == "generated" and row["artifact_id"].endswith("AircraftState")
    ]
    assert len(aircraft_generated) == 2
    assert {row["instance_id"] for row in aircraft_generated} == {
        repr(INSTANCE_A.key),
        repr(INSTANCE_B.key),
    }
