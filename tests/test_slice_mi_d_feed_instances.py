"""
Slice MI-D: Session.feed_instances(), committing several instances of
the same domain type in one call
(docs/refactor/multi_instance_execution_plan.md, Section 5).

feed() itself is untouched by this slice -- see
tests/test_slice_22e_session_feed.py, run alongside this file in every
verification pass, for proof its own behavior is unaffected.
"""

from dataclasses import dataclass

import pytest

from reed import Flow
from reed.execution.artifact_record import ArtifactOrigin
from reed.execution.instance_key import InstanceKey


@dataclass
class AircraftState:
    altitude: float


@dataclass
class OtherReading:
    value: int


def make_session():
    return Flow().session()


def test_feed_instances_commits_one_record_per_instance():
    session = make_session()

    session.feed_instances(
        {
            InstanceKey(key="A"): AircraftState(altitude=100.0),
            InstanceKey(key="B"): AircraftState(altitude=200.0),
        }
    )
    session.push()  # feed only stages the value; push() applies it (#34)

    record_a = session.repository.get_artifact_record(
        AircraftState, instance=InstanceKey(key="A")
    )
    record_b = session.repository.get_artifact_record(
        AircraftState, instance=InstanceKey(key="B")
    )

    assert record_a.value.altitude == 100.0
    assert record_b.value.altitude == 200.0
    assert record_a is not record_b


def test_feed_instances_existing_feed_is_completely_unaffected():
    session = make_session()

    session.feed(AircraftState(altitude=50.0))
    session.push()  # feed only stages the value; push() applies it (#34)

    assert session.repository.get_artifact_record(AircraftState).value.altitude == 50.0
    assert (
        session.repository.get_artifact_record(
            AircraftState, instance=InstanceKey.singleton()
        ).value.altitude
        == 50.0
    )


def test_feed_instances_rejects_mixed_domain_types():
    session = make_session()

    with pytest.raises(TypeError):
        session.feed_instances(
            {
                InstanceKey(key="A"): AircraftState(altitude=100.0),
                InstanceKey(key="B"): OtherReading(value=1),
            }
        )


def test_feed_instances_empty_mapping_is_a_no_op():
    session = make_session()

    session.feed_instances({})

    assert session.repository.get_artifact_record(AircraftState) is None


def test_feed_instances_each_instance_gets_origin_external():
    session = make_session()

    session.feed_instances({InstanceKey(key="A"): AircraftState(altitude=1.0)})
    session.push()  # feed only stages the value; push() applies it (#34)

    record = session.repository.get_artifact_record(
        AircraftState, instance=InstanceKey(key="A")
    )
    assert record.provenance.origin is ArtifactOrigin.EXTERNAL


def test_feed_instances_re_feeding_same_instance_advances_its_own_record_only():
    session = make_session()

    session.feed_instances({InstanceKey(key="A"): AircraftState(altitude=1.0)})
    session.push()  # feed only stages the value; push() applies it (#34)
    first = session.repository.get_artifact_record(
        AircraftState, instance=InstanceKey(key="A")
    )

    session.feed_instances({InstanceKey(key="A"): AircraftState(altitude=2.0)})
    session.push()  # feed only stages the value; push() applies it (#34)
    second = session.repository.get_artifact_record(
        AircraftState, instance=InstanceKey(key="A")
    )

    assert first is second
    assert second.value.altitude == 2.0
    assert second.version.number == 2
