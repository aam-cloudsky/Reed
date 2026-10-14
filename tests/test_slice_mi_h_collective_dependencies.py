"""
Slice MI-H: Collective dependencies -- a node parameter declared
`Annotated[T, Collective]` resolves the currently known collection of
instances of T (docs/refactor/multi_instance_execution_plan.md, Section
5, item 8).

Genuine fork disclosed in this slice's own SliceContract: detection uses
`Annotated[T, Collective]` (mirroring the existing `Sampled` precedent),
not a bare `Collection[T]` generic origin. A `Collective`-marked
parameter always gets `InputRole.SAMPLED` -- its own arrival never
triggers firing by itself (see collective.py's own docstring) -- so a
collective-consuming node needs at least one ordinary TRIGGERING partner
input (or `TriggerPolicy.MANUAL`) to ever fire automatically; this
composes naturally with Slice MI-G's Broadcasting (a shared, broadcast
tick is exactly that kind of TRIGGERING partner).

Explicit non-goal exercised as an assertion, not an xfail: this slice
adds no new eligibility-scheduling path for a collective dependency by
itself (quiescence -- "has every instance that will exist this
propagation already arrived" -- is jointly MI-H/MI-I's concern, not
decided here). The collective value resolved at firing time is a
straightforward, static read of repository state at that moment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import pytest

from reed import Flow, TriggerPolicy
from reed.composition.flow.artifact_dependency_graph import (
    ZeroTriggeringInputsError,
)
from reed.composition.node.collective import Collective
from reed.composition.node.sampled import Sampled
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
class FleetSummary:
    total_altitude: float
    count: int


def test_collective_parameter_resolves_the_currently_known_instances():
    seen: list[tuple[float, ...]] = []

    def fleet_summary(
        tick: DeltaT,
        states: Annotated[AircraftState, Collective],
    ) -> FleetSummary:
        altitudes = tuple(s.altitude for s in states)
        seen.append(altitudes)
        return FleetSummary(total_altitude=sum(altitudes), count=len(altitudes))

    flow = Flow()
    flow.add(fleet_summary)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=100.0),
            INSTANCE_B: AircraftState(altitude=200.0),
        }
    )
    session.feed(DeltaT(seconds=1.0))
    session.push()

    assert sorted(seen[-1]) == [100.0, 200.0]
    summary = session.repository.get_artifact_record(FleetSummary).value
    assert summary.total_altitude == 300.0
    assert summary.count == 2


def test_collective_parameter_is_an_empty_tuple_before_any_instance_commits():
    def fleet_summary(
        tick: DeltaT,
        states: Annotated[AircraftState, Collective],
    ) -> FleetSummary:
        return FleetSummary(total_altitude=sum(s.altitude for s in states), count=len(states))

    flow = Flow()
    flow.add(fleet_summary)
    session = flow.session()

    # No AircraftState has ever been fed -- the collective dependency
    # must not block coverage; it resolves to an empty collection.
    session.feed(DeltaT(seconds=1.0))
    session.push()

    summary = session.repository.get_artifact_record(FleetSummary).value
    assert summary.count == 0
    assert summary.total_altitude == 0.0


def test_collective_only_input_requires_manual_or_another_triggering_partner():
    def fleet_summary(states: Annotated[AircraftState, Collective]) -> FleetSummary:
        return FleetSummary(total_altitude=sum(s.altitude for s in states), count=len(states))

    flow = Flow()

    # A node whose ONLY consumed parameter is Collective has zero
    # TRIGGERING inputs -- rejected at registration, exactly like any
    # other all-SAMPLED node (Slice 21D's existing, unmodified guard).
    with pytest.raises(ZeroTriggeringInputsError):
        flow.add(fleet_summary)

    # Declaring it MANUAL is the existing, unmodified escape hatch.
    flow_manual = Flow()
    flow_manual.add(fleet_summary, trigger_policy=TriggerPolicy.MANUAL)  # does not raise


def test_collective_dependency_never_triggers_firing_by_itself():
    calls = []

    def fleet_summary(
        tick: DeltaT,
        states: Annotated[AircraftState, Collective],
    ) -> FleetSummary:
        calls.append(len(states))
        return FleetSummary(total_altitude=0.0, count=len(states))

    flow = Flow()
    flow.add(fleet_summary, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    session.feed(DeltaT(seconds=1.0))
    session.push()
    assert len(calls) == 1

    # A new AircraftState instance committing must NOT, by itself,
    # re-trigger fleet_summary -- its collective parameter is SAMPLED,
    # never TRIGGERING.
    session.feed_instances({INSTANCE_A: AircraftState(altitude=50.0)})
    session.push()
    assert len(calls) == 1


def test_collective_dependency_composes_with_broadcasting_as_its_triggering_partner():
    def fleet_summary(
        tick: DeltaT,
        states: Annotated[AircraftState, Collective],
    ) -> FleetSummary:
        return FleetSummary(total_altitude=sum(s.altitude for s in states), count=len(states))

    flow = Flow()
    flow.add(fleet_summary)
    session = flow.session()

    session.feed_instances({INSTANCE_A: AircraftState(altitude=10.0)})
    session.feed(DeltaT(seconds=1.0))
    session.push()

    first = session.repository.get_artifact_record(FleetSummary).value
    assert first.count == 1

    # A second broadcast tick re-fires fleet_summary (DeltaT is its
    # TRIGGERING partner, via Slice MI-G), now seeing the fleet as it
    # currently stands -- one more instance since the last tick.
    session.feed_instances({INSTANCE_B: AircraftState(altitude=20.0)})
    session.feed(DeltaT(seconds=1.0))
    session.push()

    second = session.repository.get_artifact_record(FleetSummary).value
    assert second.count == 2
    assert second.total_altitude == 30.0


def test_existing_sampled_annotation_detection_is_completely_unaffected():
    calls = []

    def joiner(
        state: AircraftState,
        offset: Annotated[DeltaT, Sampled],
    ) -> FleetSummary:
        calls.append(offset.seconds)
        return FleetSummary(total_altitude=state.altitude, count=1)

    flow = Flow()
    flow.add(joiner, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    session.feed(DeltaT(seconds=0.5))
    session.feed(AircraftState(altitude=1.0))
    session.push()

    # Sampled still contributes to coverage but never triggers by
    # itself, exactly as before Slice MI-H introduced Collective.
    assert calls == [0.5]
