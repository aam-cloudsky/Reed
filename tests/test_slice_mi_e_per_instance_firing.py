"""
Slice MI-E: per-instance eligibility and firing through push()'s cascade
(docs/refactor/multi_instance_execution_plan.md, Section 5).

Explicit non-goals exercised as absence, not tested here (see this
slice's own SliceContract): Broadcasting a singleton-scoped dependency
into a per-instance firing (MI-G), and per-instance NodeMemory/last_output
(MI-F) -- every node below either has no NodeContext parameter, or its
memory/last_output behavior under multiplicity is deliberately left
unasserted.
"""

from dataclasses import dataclass

from reed import Flow, TriggerPolicy
from reed.execution.instance_key import InstanceKey


@dataclass
class AircraftState:
    altitude: float


@dataclass
class Observation:
    altitude: float


@dataclass
class ControlCommand:
    delta: float


def perception(state: AircraftState) -> Observation:
    return Observation(altitude=state.altitude)


def test_node_fires_once_per_known_instance():
    calls = []

    def recording_perception(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(recording_perception)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=100.0),
            InstanceKey(key="B"): AircraftState(altitude=200.0),
        }
    )
    session.push()

    assert sorted(calls) == [100.0, 200.0]


def test_each_instance_firing_commits_to_its_own_repository_slot():
    flow = Flow()
    flow.add(perception)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=100.0),
            InstanceKey(key="B"): AircraftState(altitude=200.0),
        }
    )
    session.push()

    obs_a = session.repository.get_artifact_record(
        Observation, instance=InstanceKey(key="A")
    )
    obs_b = session.repository.get_artifact_record(
        Observation, instance=InstanceKey(key="B")
    )

    assert obs_a.value.altitude == 100.0
    assert obs_b.value.altitude == 200.0
    assert obs_a is not obs_b


def test_all_inputs_changed_eligibility_is_evaluated_per_instance():
    calls = []

    def joiner(state: AircraftState, obs: Observation) -> ControlCommand:
        calls.append((state.altitude, obs.altitude))
        return ControlCommand(delta=0.0)

    flow = Flow()
    flow.add(joiner, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    # Only AircraftState<A> and Observation<A> arrive: instance B is not
    # yet fully covered and must not fire.
    session.feed_instances({InstanceKey(key="A"): AircraftState(altitude=1.0)})
    session.feed_instances({InstanceKey(key="A"): Observation(altitude=2.0)})
    session.feed_instances({InstanceKey(key="B"): AircraftState(altitude=3.0)})
    session.push()

    assert calls == [(1.0, 2.0)]


def test_any_input_changed_eligibility_is_evaluated_per_instance():
    calls = []

    def single_input(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(single_input, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=1.0),
            InstanceKey(key="B"): AircraftState(altitude=2.0),
        }
    )
    session.push()

    assert sorted(calls) == [1.0, 2.0]


def test_manual_policy_still_never_fires_via_the_cascade_per_instance():
    calls = []

    def manual_node(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(manual_node, trigger_policy=TriggerPolicy.MANUAL)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=1.0),
            InstanceKey(key="B"): AircraftState(altitude=2.0),
        }
    )
    session.push()

    assert calls == []


def test_cascade_propagates_the_firing_instance_to_downstream_consumers():
    def control(obs: Observation) -> ControlCommand:
        return ControlCommand(delta=obs.altitude / 10.0)

    flow = Flow()
    flow.add(perception)
    flow.add(control)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=100.0),
            InstanceKey(key="B"): AircraftState(altitude=200.0),
        }
    )
    session.push()

    cmd_a = session.repository.get_artifact_record(
        ControlCommand, instance=InstanceKey(key="A")
    )
    cmd_b = session.repository.get_artifact_record(
        ControlCommand, instance=InstanceKey(key="B")
    )

    assert cmd_a.value.delta == 10.0
    assert cmd_b.value.delta == 20.0


def test_second_push_with_no_intervening_feed_is_a_no_op_per_instance():
    calls = []

    def counting_perception(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(counting_perception)
    session = flow.session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=1.0),
            InstanceKey(key="B"): AircraftState(altitude=2.0),
        }
    )
    session.push()
    assert len(calls) == 2

    session.push()
    assert len(calls) == 2


def test_singleton_instance_path_is_completely_unaffected():
    calls = []

    def counting_perception(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(counting_perception)
    session = flow.session()

    session.feed(AircraftState(altitude=42.0))
    session.push()

    assert calls == [42.0]
    assert session.repository.get_artifact_record(Observation).value.altitude == 42.0
