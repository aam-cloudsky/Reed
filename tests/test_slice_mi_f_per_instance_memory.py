"""
Slice MI-F: NodeMemory scope decision (R4) and per-instance wiring
(docs/refactor/multi_instance_execution_plan.md, Section 5, item 6).

Decision recorded here and in this slice's own SliceContract /
docs/refactor/multi_instance_state.md: NodeMemory and last_output are
per-instance (one independent memory object and one independent
last-committed-output slot per (Session, NodeSession, InstanceKey)
triple), not shared across every instance a node fires for. The
zero-argument `.memory` / `.last_output` / `.context` properties on
`NodeSession` keep reading through `InstanceKey.singleton()`, so every
pre-multi-instance call site is unaffected -- exercised here as
regression coverage, not just assumed.

Explicit non-goal exercised as absence, not tested here: NodeSession
`.firing_lock` (architectural_invariants.md #17) deliberately stays
scoped to (Session, NodeSession) only, not split per instance -- see
this slice's own SliceContract for why.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed import Flow, NodeContext
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


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


@dataclass
class Measurement:
    value: int


@dataclass
class Estimate:
    value: int


INSTANCE_A = InstanceKey(key="A")
INSTANCE_B = InstanceKey(key="B")


def test_two_instances_of_the_same_node_get_independent_memory_objects():
    seen_memory: list[object] = []

    def track(
        ctx: NodeContext[TrackerMemory, Observation],
        state: AircraftState,
    ) -> Observation:
        seen_memory.append(ctx.memory)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
        }
    )
    session.push()

    assert len(seen_memory) == 2
    assert seen_memory[0] is not seen_memory[1]


def test_two_instances_of_the_same_node_get_independent_last_output():
    seen: list[tuple[float, float | None]] = []

    def track(
        ctx: NodeContext[TrackerMemory, Observation],
        state: AircraftState,
    ) -> Observation:
        previous = ctx.last_output.altitude if ctx.last_output is not None else None
        seen.append((state.altitude, previous))
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    # Both instances' first firing: no prior committed output for either.
    assert all(previous is None for _, previous in seen)

    session.feed_instances({INSTANCE_A: AircraftState(altitude=101.0)})
    session.push()

    # Instance A's second firing must see its OWN last committed output
    # (100.0), never instance B's (200.0) -- last_output is per instance,
    # not one shared slot across every instance of this node.
    assert seen[-1] == (101.0, 100.0)


def test_memory_is_memoized_per_instance_across_repeated_access():
    def track(
        ctx: NodeContext[TrackerMemory, Observation],
        state: AircraftState,
    ) -> Observation:
        previous = ctx.memory.previous_confidence
        ctx.memory.previous_confidence = state.altitude
        return Observation(altitude=previous if previous is not None else -1.0)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    # First firing for each instance: memory starts empty (fresh object).
    assert session.repository.get_artifact_record(
        Observation, instance=INSTANCE_A
    ).value.altitude == -1.0
    assert session.repository.get_artifact_record(
        Observation, instance=INSTANCE_B
    ).value.altitude == -1.0

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=150.0),
            INSTANCE_B: AircraftState(altitude=250.0),
        }
    )
    session.push()

    # Second firing: each instance's memory recalls its OWN first-firing
    # altitude (memoized, mutated in place), never the other instance's --
    # proving both memoization and isolation together.
    assert session.repository.get_artifact_record(
        Observation, instance=INSTANCE_A
    ).value.altitude == 100.0
    assert session.repository.get_artifact_record(
        Observation, instance=INSTANCE_B
    ).value.altitude == 200.0


def test_zero_arg_memory_property_reads_the_singleton_instance():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.memory.previous_confidence = measurement.value / 10
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    session.feed(Measurement(6))
    session.push()

    assert session.node_session(track).memory.previous_confidence == 0.6


def test_zero_arg_last_output_property_reads_the_singleton_instance():
    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    session = flow.session()

    assert session.node_session(track).last_output is None

    session.feed(Measurement(4))
    session.push()

    assert session.node_session(track).last_output.value == 4


def test_real_firing_through_push_gives_each_instance_its_own_memory_and_last_output():
    def perception(
        ctx: NodeContext[TrackerMemory, Observation],
        state: AircraftState,
    ) -> Observation:
        ctx.memory.previous_confidence = state.altitude
        return Observation(altitude=state.altitude)

    def control(
        ctx: NodeContext[TrackerMemory, ControlCommand],
        obs: Observation,
    ) -> ControlCommand:
        previous = ctx.last_output.delta if ctx.last_output is not None else None
        ctx.memory.previous_confidence = obs.altitude
        return ControlCommand(delta=obs.altitude / 10.0 + (previous or 0.0))

    flow = Flow()
    flow.add(perception)
    flow.add(control)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.push()

    perception_session = session.node_session(perception)
    control_session = session.node_session(control)

    # Both nodes' memory is per instance: firing for A must not leave any
    # trace on B's own memory object, in either node of the cascade.
    cmd_a = session.repository.get_artifact_record(
        ControlCommand, instance=INSTANCE_A
    )
    cmd_b = session.repository.get_artifact_record(
        ControlCommand, instance=INSTANCE_B
    )
    assert cmd_a.value.delta == 10.0
    assert cmd_b.value.delta == 20.0

    session.feed_instances({INSTANCE_A: AircraftState(altitude=110.0)})
    session.push()

    # Instance A's second cascade sees its own prior ControlCommand
    # (10.0) as last_output, never instance B's (20.0).
    cmd_a_2 = session.repository.get_artifact_record(
        ControlCommand, instance=INSTANCE_A
    )
    assert cmd_a_2.value.delta == 11.0 + 10.0

    # The zero-argument (singleton) properties on these same NodeSessions
    # remain independent of both instances -- nothing above ever touched
    # the singleton path.
    assert perception_session.last_output is None
    assert control_session.last_output is None


def test_node_with_no_context_parameter_still_raises_attribute_error_for_any_instance():
    def stateless(state: AircraftState) -> Observation:
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(stateless)
    session = flow.session()

    node_session = session.node_session(stateless)

    assert not hasattr(node_session, "memory")
    assert not hasattr(node_session, "last_output")
    assert not hasattr(node_session, "context")

    with pytest.raises(AttributeError):
        node_session.memory

    with pytest.raises(AttributeError):
        node_session.last_output

    with pytest.raises(AttributeError):
        node_session._memory_for(INSTANCE_A)

    with pytest.raises(AttributeError):
        node_session._last_output_for(INSTANCE_A)
