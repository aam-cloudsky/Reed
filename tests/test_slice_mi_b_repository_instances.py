"""
Slice MI-B: ArtifactRepository storage generalized to (domain type,
InstanceKey) (docs/refactor/multi_instance_execution_plan.md, Section 5).

Every pre-existing regression test that calls set_artifact_record(record)
or get_artifact_record(domain_type) / get(domain_type) with no `instance`
argument continues to exercise exactly the same single-instance behavior
(tests/test_slice_22d_shared_commit_path.py, tests/test_slice_2f_on_output_dispatch.py,
tests/test_observability_o7b_provenance_version.py, and others) -- this
file adds coverage for the new (type, instance) dimension itself, it does
not replace or narrow any of those.
"""

from dataclasses import dataclass

from reed.execution.artifact_record import ArtifactRecord
from reed.execution.instance_key import InstanceKey
from reed.synchronization.artifact_repository import ArtifactRepository
from reed.transportation.bus import Bus


@dataclass
class Widget:
    value: int


def make_repository() -> ArtifactRepository:
    return ArtifactRepository(bus=Bus.create())


def test_default_instance_roundtrips_exactly_like_before():
    repository = make_repository()
    record = ArtifactRecord(value=Widget(value=1))

    repository.set_artifact_record(record)

    assert repository.get_artifact_record(Widget) is record
    assert repository.get(Widget) is record


def test_two_distinct_instances_of_the_same_type_do_not_clobber_each_other():
    repository = make_repository()
    record_a = ArtifactRecord(value=Widget(value=1))
    record_b = ArtifactRecord(value=Widget(value=2))

    repository.set_artifact_record(record_a, instance=InstanceKey(key="A"))
    repository.set_artifact_record(record_b, instance=InstanceKey(key="B"))

    assert repository.get_artifact_record(Widget, instance=InstanceKey(key="A")) is record_a
    assert repository.get_artifact_record(Widget, instance=InstanceKey(key="B")) is record_b


def test_unknown_instance_returns_none():
    repository = make_repository()
    repository.set_artifact_record(
        ArtifactRecord(value=Widget(value=1)), instance=InstanceKey(key="A")
    )

    assert repository.get_artifact_record(Widget, instance=InstanceKey(key="B")) is None


def test_default_instance_is_independent_from_a_named_instance():
    repository = make_repository()
    default_record = ArtifactRecord(value=Widget(value=1))
    named_record = ArtifactRecord(value=Widget(value=2))

    repository.set_artifact_record(default_record)
    repository.set_artifact_record(named_record, instance=InstanceKey(key="A"))

    assert repository.get_artifact_record(Widget) is default_record
    assert repository.get_artifact_record(Widget, instance=InstanceKey(key="A")) is named_record


def test_get_all_artifact_records_returns_every_committed_instance():
    repository = make_repository()
    record_a = ArtifactRecord(value=Widget(value=1))
    record_b = ArtifactRecord(value=Widget(value=2))
    repository.set_artifact_record(record_a, instance=InstanceKey(key="A"))
    repository.set_artifact_record(record_b, instance=InstanceKey(key="B"))

    all_records = repository.get_all_artifact_records(Widget)

    assert dict(all_records) == {
        InstanceKey(key="A"): record_a,
        InstanceKey(key="B"): record_b,
    }


def test_get_all_artifact_records_is_empty_for_an_uncommitted_type():
    repository = make_repository()

    assert dict(repository.get_all_artifact_records(Widget)) == {}


def test_get_all_artifact_records_under_default_instance_matches_get_artifact_record():
    repository = make_repository()
    record = ArtifactRecord(value=Widget(value=7))
    repository.set_artifact_record(record)

    all_records = repository.get_all_artifact_records(Widget)

    assert dict(all_records) == {InstanceKey.singleton(): record}
    assert all_records[InstanceKey.singleton()] is repository.get_artifact_record(Widget)
