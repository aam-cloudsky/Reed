"""
Two genuine correctness bugs found by an independent, adversarial review
of the whole "Support multiple artifact instances and per-instance node
execution" feature (slices MI-A through MI-J), performed after MI-J's own
review had already signed off. Both are fixed here, disclosed in
docs/refactor/multi_instance_state.md's own Decision log, rather than
silently folded into an earlier slice's own test file.

1. `Session.snapshot()` (and `Session.invoke()`, which calls it) crashed
   with `AttributeError` for any domain type committed only via
   `feed_instances(...)` and never via plain `feed()` -- i.e. exactly the
   pure multi-instance use case this whole feature exists to support.
   `Snapshot.from_repository` assumed a singleton-scoped record always
   existed for every domain type it found in the repository's keys; fixed
   by reading every currently known instance (`ArtifactRepository.
   get_all_artifact_records`) instead, and by giving `Snapshot` a new
   `.instances(domain_type)` accessor so the multi-instance state is
   actually reachable rather than silently invisible through the
   pre-existing single-value `.get`/`[...]` surface.

2. A singleton-scoped ("broadcast", Slice MI-G) dependency's own
   freshness never expired: `Session._fire`'s per-firing freshness clear
   only clears `_fresh_since_last_firing[flow_node][instance]` for the
   firing's own instance, never the separate singleton-scope entry a
   broadcast type's freshness lives in. Under `TriggerPolicy.
   ALL_INPUTS_CHANGED` (the default trigger_policy for `Flow.add(...)`),
   this meant a node mixing a broadcast dependency with a per-instance
   one would spuriously re-fire on every later per-instance arrival, even
   when the broadcast type itself was never fed again -- silently
   degrading ALL_INPUTS_CHANGED to ANY_INPUT_CHANGED behavior for exactly
   the combination (broadcasting + the default trigger policy) the plan
   document's own aircraft example uses. Fixed in `Session.push()`: the
   singleton-scope freshness entry for any flow_node that fired under
   ALL_INPUTS_CHANGED is now cleared once, after the entire push() call's
   seed pass and cascade both finish -- not per-firing, so every instance
   covered this same push() call still gets a fair look at a genuinely
   new broadcast freshness event before it is spent.

3. `graph.render_provenance_tree`'s new `[instance=<instance_id>]`
   suffix (Slice MI-J) was silently swallowed by Rich: `Tree`/`Console`
   interpret `[...]` in a label as markup syntax, not literal text, so
   `[instance='N-ALPHA']` was parsed as an unrecognized markup tag and
   dropped rather than displayed -- found by
   examples/multi_instance_fleet_example.py, which is the first place
   this method was ever exercised for a genuinely multi-instance flow
   (MI-J's own tests only rendered the singleton-only case, where the
   suffix is empty and this never triggers). Fixed by passing every
   label through `rich.markup.escape(...)` before handing it to
   `Tree.add(...)`.
"""

from __future__ import annotations

from dataclasses import dataclass

from reed import Flow
from reed.execution.instance_key import InstanceKey
from reed.observability.graph import render_provenance_tree

INSTANCE_A = InstanceKey(key="A")
INSTANCE_B = InstanceKey(key="B")


@dataclass
class AircraftState:
    altitude: float


@dataclass
class DeltaT:
    seconds: float


@dataclass
class Observation:
    altitude: float


def test_snapshot_does_not_crash_for_a_type_committed_only_via_feed_instances():
    flow = Flow()
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
        }
    )

    # Before the fix: AttributeError, 'NoneType' object has no attribute
    # 'value' -- AircraftState is a key in the repository (both A and B
    # are committed) but has no record at InstanceKey.singleton().
    snapshot = session.snapshot()

    # The pre-existing single-value surface correctly reports "nothing at
    # singleton scope" rather than crashing or fabricating a value.
    assert snapshot.get(AircraftState) is None
    import pytest

    with pytest.raises(KeyError):
        snapshot[AircraftState]

    # The new multi-instance-aware accessor is where the actual state is.
    instances = snapshot.instances(AircraftState)
    assert instances[INSTANCE_A].altitude == 1.0
    assert instances[INSTANCE_B].altitude == 2.0
    assert len(instances) == 2


def test_snapshot_get_and_getitem_are_unaffected_for_a_singleton_only_flow():
    def calibrate(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(calibrate)
    session = flow.session()

    snapshot = session.invoke(AircraftState(altitude=42.0))

    assert snapshot[Observation].altitude == 42.0
    assert snapshot.get(Observation).altitude == 42.0
    assert snapshot.get(DeltaT) is None
    assert snapshot.instances(Observation) == {
        InstanceKey.singleton(): snapshot[Observation]
    }


def test_snapshot_instance_keyword_reaches_one_specific_instance():
    flow = Flow()
    session = flow.session()

    session.feed_instances(
        {INSTANCE_A: AircraftState(altitude=10.0), INSTANCE_B: AircraftState(altitude=20.0)}
    )
    snapshot = session.snapshot()

    assert snapshot.get(AircraftState, instance=INSTANCE_A).altitude == 10.0
    assert snapshot.get(AircraftState, instance=INSTANCE_B).altitude == 20.0
    assert snapshot.get(AircraftState, instance=InstanceKey(key="C")) is None


def test_broadcast_freshness_expires_after_one_push_under_all_inputs_changed():
    calls: list[tuple[float, float]] = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append((state.altitude, dt.seconds))
        return Observation(altitude=state.altitude + dt.seconds)

    flow = Flow()
    flow.add(perception)  # default TriggerPolicy.ALL_INPUTS_CHANGED
    session = flow.session()

    session.feed(DeltaT(seconds=1.0))
    session.feed_instances({INSTANCE_A: AircraftState(altitude=100.0)})
    session.push()
    assert calls == [(100.0, 1.0)]

    # No new DeltaT fed at all -- before the fix, this spuriously refired
    # perception on every subsequent per-instance arrival, since the
    # broadcast type's own freshness never expired.
    session.feed_instances({INSTANCE_A: AircraftState(altitude=101.0)})
    session.push()
    assert calls == [(100.0, 1.0)], "must NOT refire: DeltaT never changed since last firing"

    session.feed_instances({INSTANCE_A: AircraftState(altitude=102.0)})
    session.push()
    assert calls == [(100.0, 1.0)], "must NOT refire on a second stale push() either"

    # Re-feeding the broadcast value correctly re-enables firing.
    session.feed(DeltaT(seconds=2.0))
    session.feed_instances({INSTANCE_A: AircraftState(altitude=103.0)})
    session.push()
    assert calls == [(100.0, 1.0), (103.0, 2.0)]


def test_broadcast_freshness_is_not_spent_prematurely_within_one_push_across_instances():
    calls: list[tuple[float, float]] = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append((state.altitude, dt.seconds))
        return Observation(altitude=state.altitude + dt.seconds)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    # A naive "clear singleton freshness as soon as any instance fires"
    # fix would incorrectly deny the SECOND instance evaluated in the
    # same push() call the same freshness event the first instance just
    # used. Both A and B must still fire together here.
    session.feed(DeltaT(seconds=1.0))
    session.feed_instances(
        {INSTANCE_A: AircraftState(altitude=100.0), INSTANCE_B: AircraftState(altitude=200.0)}
    )
    session.push()

    assert sorted(calls) == [(100.0, 1.0), (200.0, 1.0)]


def test_provenance_tree_instance_suffix_survives_rich_markup_escaping(tmp_path):
    from rich.console import Console

    def track(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(track)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed_instances(
        {INSTANCE_A: AircraftState(altitude=1.0), INSTANCE_B: AircraftState(altitude=2.0)}
    )
    session.push()

    run_dir = root / "runs" / session.execution_id
    tree = render_provenance_tree(run_dir)

    console = Console(record=True, width=200)
    console.print(tree)
    output = console.export_text()

    # Before the fix: Rich's markup parser silently swallowed
    # "[instance='A']"-shaped text, leaving no trace of it (and no
    # error) in the rendered output.
    assert f"[instance={repr(INSTANCE_A.key)}]" in output
    assert f"[instance={repr(INSTANCE_B.key)}]" in output
