"""
Slice MI-I: Lifecycle (instance removal/replacement) and fault isolation
(R9) (docs/refactor/multi_instance_execution_plan.md, Section 5, item
9).

Decisions recorded here and in this slice's own SliceContract /
docs/refactor/multi_instance_state.md:

  - Removal is genuinely new (`Session.remove_instance` /
    `ArtifactRepository.remove_artifact_record`), scoped to exactly one
    (domain type, instance) pair. Replacement already worked via
    existing MI-B/MI-D machinery -- exercised here as a regression
    confirmation, not new code.
  - R9: a firing failure for any one instance ABORTS the whole push()
    propagation -- Session._fire's own pre-existing, unmodified
    exception handling, not a new isolation mechanism. Exercised here as
    a passing assertion, not an xfail: sibling instances already queued
    in the same cascade never fire once one instance's firing raises.
  - Quiescence is caller-controlled: push() is fully synchronous and
    sequential, so a Collective dependency's read reflects exactly what
    has committed, in FIFO cascade order, by the time execution reaches
    that firing -- no new synchronization primitive is needed or added.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from reed import Collective, Flow, InstanceKey

INSTANCE_A = InstanceKey(key="A")
INSTANCE_B = InstanceKey(key="B")


@dataclass
class AircraftState:
    altitude: float


@dataclass
class Observation:
    altitude: float


@dataclass
class DeltaT:
    seconds: float


@dataclass
class FleetSummary:
    count: int


def test_replacing_an_already_known_instance_works_via_existing_machinery():
    flow = Flow()
    session = flow.session()

    session.feed_instances({INSTANCE_A: AircraftState(altitude=100.0)})
    session.feed_instances({INSTANCE_A: AircraftState(altitude=150.0)})

    record = session.repository.get_artifact_record(
        AircraftState, instance=INSTANCE_A
    )
    assert record.value.altitude == 150.0
    assert record.version.number == 2


def test_removed_instance_disappears_from_the_repository():
    flow = Flow()
    session = flow.session()

    session.feed_instances({INSTANCE_A: AircraftState(altitude=100.0)})
    assert session.repository.get_artifact_record(
        AircraftState, instance=INSTANCE_A
    ) is not None

    removed = session.remove_instance(AircraftState, INSTANCE_A)

    assert removed is True
    assert (
        session.repository.get_artifact_record(AircraftState, instance=INSTANCE_A)
        is None
    )


def test_removed_instance_disappears_from_a_collective_dependencys_view():
    def fleet_summary(
        tick: DeltaT,
        states: Collective[AircraftState],
    ) -> FleetSummary:
        return FleetSummary(count=len(states))

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
    assert session.repository.get_artifact_record(FleetSummary).value.count == 2

    session.remove_instance(AircraftState, INSTANCE_A)
    session.feed(DeltaT(seconds=1.0))
    session.push()

    assert session.repository.get_artifact_record(FleetSummary).value.count == 1


def test_removed_instance_no_longer_blocks_or_satisfies_coverage_from_stale_state():
    calls = []

    def perception(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    session.feed_instances({INSTANCE_A: AircraftState(altitude=1.0)})
    session.push()
    assert calls == [1.0]

    session.remove_instance(AircraftState, INSTANCE_A)

    # A second push() with no intervening feed for A must not resurrect
    # a firing from the now-removed, stale last-known value.
    session.push()
    assert calls == [1.0]

    # Feeding instance A again after removal works exactly like a fresh
    # first arrival.
    session.feed_instances({INSTANCE_A: AircraftState(altitude=2.0)})
    session.push()
    assert calls == [1.0, 2.0]


def test_removing_an_unknown_instance_is_a_tolerant_no_op():
    flow = Flow()
    session = flow.session()

    removed = session.remove_instance(AircraftState, INSTANCE_A)

    assert removed is False


def test_a_firing_failure_for_one_instance_aborts_the_whole_propagation():
    calls = []

    def perception(state: AircraftState) -> Observation:
        calls.append(state.altitude)
        if state.altitude < 0:
            raise ValueError("negative altitude")
        return Observation(altitude=state.altitude)

    flow = Flow()
    flow.add(perception)
    session = flow.session()

    # Instance A is seeded first (dict insertion order) and will raise;
    # instance B is seeded second and must never fire once A's firing
    # aborts the propagation.
    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=-1.0),
            INSTANCE_B: AircraftState(altitude=5.0),
        }
    )

    with pytest.raises(ValueError, match="negative altitude"):
        session.push()

    assert calls == [-1.0]
    assert (
        session.repository.get_artifact_record(Observation, instance=INSTANCE_B)
        is None
    )


def test_quiescence_is_caller_controlled_via_feed_instances_then_push():
    def fleet_summary(
        tick: DeltaT,
        states: Collective[AircraftState],
    ) -> FleetSummary:
        return FleetSummary(count=len(states))

    flow = Flow()
    flow.add(fleet_summary)
    session = flow.session()

    # Feeding a complete batch before push() means every instance in the
    # batch is committed before fleet_summary's own eligibility is even
    # evaluated -- the collective read below is guaranteed to see all
    # three, deterministically, with no synchronization primitive beyond
    # ordinary call sequencing.
    session.feed_instances(
        {
            INSTANCE_A: AircraftState(altitude=1.0),
            INSTANCE_B: AircraftState(altitude=2.0),
            InstanceKey(key="C"): AircraftState(altitude=3.0),
        }
    )
    session.feed(DeltaT(seconds=1.0))
    session.push()

    assert session.repository.get_artifact_record(FleetSummary).value.count == 3
