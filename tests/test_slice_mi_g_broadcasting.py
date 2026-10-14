"""
Slice MI-G: Broadcasting -- a singleton-scoped dependency (no instance
dimension of its own, such as a shared DeltaT fed once via plain
`feed()`) participates correctly as an input in every per-instance
firing that consumes it (docs/refactor/multi_instance_execution_plan.md,
Section 5, item 7).

Explicit non-goal exercised as a passing assertion, not an xfail: this
slice does not change WHEN a node is attempted (push()'s seed selection
and cascade dispatch are unchanged), only what values an attempted
firing can see. Updating only the broadcast value does not, by itself,
retroactively re-trigger an instance that has no fresh input of its own
this push() -- see this slice's own SliceContract for why that
scheduling question is deferred to MI-H/MI-I, not silently assumed here.
"""

from __future__ import annotations

from dataclasses import dataclass

from reed import Flow, TriggerPolicy
from reed.execution.instance_key import InstanceKey

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


@dataclass
class ControlCommand:
    delta: float


def test_per_instance_node_reads_a_singleton_scoped_broadcast_dependency():
    calls = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append((state.altitude, dt.seconds))
        return Observation(altitude=state.altitude + dt.seconds)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    # The broadcast dependency is fed once, at singleton scope, never per
    # instance -- exactly DeltaT's own role in the plan document's
    # aircraft example.
    session.feed(DeltaT(seconds=0.5))

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    assert sorted(calls) == [(100.0, 0.5), (200.0, 0.5)]

    obs_a = session.repository.get_artifact_record(
        Observation, instance=INSTANCE_A
    )
    obs_b = session.repository.get_artifact_record(
        Observation, instance=INSTANCE_B
    )
    assert obs_a.value.altitude == 100.5
    assert obs_b.value.altitude == 200.5


def test_all_inputs_changed_eligibility_merges_singleton_freshness_with_instance_freshness():
    calls = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(perception, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    # AircraftState<A> arrives, but DeltaT has never been fed at all --
    # not fully covered, must not fire.
    session.feed_instances({INSTANCE_A: AircraftState(altitude=1.0)})
    session.push()
    assert calls == []

    # DeltaT is now fed, once, at singleton scope. ALL_INPUTS_CHANGED
    # requires every TRIGGERING type fresh at once for this instance --
    # DeltaT's freshness came from a completely different scope
    # (singleton, not A), so this only fires if broadcasting correctly
    # merges that freshness into instance A's own effective fresh set.
    session.feed(DeltaT(seconds=0.1))
    session.push()

    assert calls == [1.0]


def test_instance_specific_value_overrides_the_singleton_broadcast_value_for_the_same_type():
    calls = []

    def perception(dt: DeltaT) -> Observation:
        calls.append(dt.seconds)
        return Observation(altitude=dt.seconds)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    session.feed(DeltaT(seconds=0.1))
    session.feed_instances({INSTANCE_A: DeltaT(seconds=99.0)})
    session.push()

    obs_a = session.repository.get_artifact_record(
        Observation, instance=INSTANCE_A
    )
    # Instance A has its OWN DeltaT value fed directly -- it must use
    # that, not silently fall back to the singleton broadcast value for
    # the same type.
    assert obs_a.value.altitude == 99.0


def test_broadcast_dependency_participates_correctly_mid_cascade():
    def perception(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    def control(obs: Observation, dt: DeltaT) -> ControlCommand:
        return ControlCommand(delta=obs.altitude * dt.seconds)

    flow = Flow()
    flow.add(perception)
    flow.add(control)
    session = flow.session()

    session.feed(DeltaT(seconds=2.0))
    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=10.0),
            INSTANCE_B: AircraftState(altitude=20.0),
        }
    )
    session.push()

    # `control` never received DeltaT under INSTANCE_A or INSTANCE_B
    # directly -- only Observation arrives per instance via the cascade.
    # The broadcast merge must apply mid-cascade exactly as it does at
    # the top-level seed phase.
    cmd_a = session.repository.get_artifact_record(
        ControlCommand, instance=INSTANCE_A
    )
    cmd_b = session.repository.get_artifact_record(
        ControlCommand, instance=INSTANCE_B
    )
    assert cmd_a.value.delta == 20.0
    assert cmd_b.value.delta == 40.0


def test_updating_only_the_broadcast_value_does_not_retroactively_refire_an_untouched_instance():
    calls = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append((state.altitude, dt.seconds))
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(perception, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(DeltaT(seconds=0.1))
    session.feed_instances({INSTANCE_A: AircraftState(altitude=1.0)})
    session.push()
    assert calls == [(1.0, 0.1)]

    # Explicit non-goal (see SliceContract): refeeding only the broadcast
    # value, with no new arrival for instance A itself, does not
    # retroactively re-attempt instance A this push() -- there is no
    # fresh entry seeded under A or under singleton-as-A.
    session.feed(DeltaT(seconds=0.2))
    session.push()

    assert calls == [(1.0, 0.1)]


def test_singleton_only_flow_is_completely_unaffected():
    calls = []

    def perception(state: AircraftState, dt: DeltaT) -> Observation:
        calls.append((state.altitude, dt.seconds))
        return Observation(altitude=state.altitude + dt.seconds)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    session.feed(AircraftState(altitude=5.0))
    session.feed(DeltaT(seconds=1.0))
    session.push()

    assert calls == [(5.0, 1.0)]
    assert session.repository.get_artifact_record(Observation).value.altitude == 6.0
