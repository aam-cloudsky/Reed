"""
Slice MI-H: Collective dependencies -- a node parameter declared
`Collective[T]` resolves the currently known collection of
instances of T (docs/refactor/multi_instance_execution_plan.md, Section
5, item 8).

Genuine fork disclosed in this slice's own SliceContract: detection uses
`Collective[T]` (mirroring the existing `Sampled` precedent),
not a bare `Collection[T]` generic origin.

Issue #31 changed the input role: a `Collective` parameter was originally
`InputRole.SAMPLED`, because without a superstep barrier every instance
committed on its own and a triggering collective input would have fired
the node once per instance, on a partial set. With the barrier, every
instance committed at one barrier (or in one `feed_instances()` call)
arrives as a single change, so a `Collective` parameter is now TRIGGERING
and a fan-in fires once, after every worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from reed import Collective, Flow, InstanceKey, Sampled, TriggerPolicy

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
        states: Collective[AircraftState],
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
        states: Collective[AircraftState],
    ) -> FleetSummary:
        return FleetSummary(
            total_altitude=sum(s.altitude for s in states), count=len(states)
        )

    flow = Flow()
    # ANY_INPUT_CHANGED: the tick alone fires the node (issue #31 made the
    # Collective input triggering; under ALL_INPUTS_CHANGED the node would
    # also wait for a first batch of instances).
    flow.add(fleet_summary, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    session = flow.session()

    # No AircraftState has ever been fed -- the collective dependency
    # must not block coverage; it resolves to an empty collection.
    session.feed(DeltaT(seconds=1.0))
    session.push()

    summary = session.repository.get_artifact_record(FleetSummary).value
    assert summary.count == 0
    assert summary.total_altitude == 0.0


def test_collective_only_input_fires_once_per_batch_of_instances():
    # Issue #31 (reverses the Slice MI-H rule): a Collective input is
    # TRIGGERING. A node whose only input is Collective registers without
    # ZeroTriggeringInputsError and fires once per batch of instances.
    calls: list[int] = []

    def fleet_summary(states: Collective[AircraftState]) -> FleetSummary:
        calls.append(len(states))
        return FleetSummary(
            total_altitude=sum(s.altitude for s in states), count=len(states)
        )

    flow = Flow()
    flow.add(fleet_summary)
    session = flow.session()

    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
        }
    )
    session.push()
    assert calls == [2]

    session.push()
    assert calls == [2], "no new instances: no new firing"


def test_collective_batch_counts_as_one_arrival_under_all_inputs_changed():
    calls: list[int] = []

    def fleet_summary(
        tick: DeltaT,
        states: Collective[AircraftState],
    ) -> FleetSummary:
        calls.append(len(states))
        return FleetSummary(total_altitude=0.0, count=len(states))

    flow = Flow()
    flow.add(fleet_summary, trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED)
    session = flow.session()

    # The tick alone is not enough: ALL_INPUTS_CHANGED also waits for the
    # Collective input, which has not changed yet.
    session.feed(DeltaT(seconds=1.0))
    session.push()
    assert calls == []

    # One feed_instances() call is one arrival, however many instances it
    # carries: the node fires once, seeing both.
    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=50.0),
            INSTANCE_B: AircraftState(altitude=60.0),
        }
    )
    session.push()
    assert calls == [2]


def test_collective_dependency_composes_with_broadcasting_as_its_triggering_partner():
    def fleet_summary(
        tick: DeltaT,
        states: Collective[AircraftState],
    ) -> FleetSummary:
        return FleetSummary(
            total_altitude=sum(s.altitude for s in states), count=len(states)
        )

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
