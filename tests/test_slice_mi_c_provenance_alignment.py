"""
Slice MI-C: ArtifactProvenance.dependency_instances, additive bookkeeping
for which instance of each dependency type a provenance revision was
aligned against (docs/refactor/multi_instance_execution_plan.md, Section
5). Mirrors tests/test_slice_2c_artifact_record.py's own coverage of
`dependencies`, at unit level -- no real node firing populates either
field yet (see this slice's own SliceContract).
"""

from dataclasses import dataclass

from reed.execution.artifact_record import (
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactRecord,
)
from reed.execution.instance_key import InstanceKey


@dataclass
class Measurement:
    value: float


def test_dependency_instances_defaults_to_empty():
    provenance = ArtifactProvenance()

    assert provenance.dependency_instances == {}


def test_advance_sets_dependency_instances_when_given():
    provenance = ArtifactProvenance()

    provenance.advance(
        origin=ArtifactOrigin.NODE,
        dependency_instances={Measurement: InstanceKey(key="A")},
    )

    assert provenance.dependency_instances == {Measurement: InstanceKey(key="A")}


def test_advance_preserves_dependency_instances_when_not_given():
    provenance = ArtifactProvenance()
    provenance.advance(
        origin=ArtifactOrigin.NODE,
        dependency_instances={Measurement: InstanceKey(key="A")},
    )

    provenance.advance(origin=ArtifactOrigin.NODE)

    assert provenance.dependency_instances == {Measurement: InstanceKey(key="A")}


def test_copy_carries_dependency_instances_independently():
    provenance = ArtifactProvenance()
    provenance.advance(
        origin=ArtifactOrigin.NODE,
        dependency_instances={Measurement: InstanceKey(key="A")},
    )

    copied = provenance.copy()
    copied.dependency_instances[Measurement] = InstanceKey(key="B")

    assert provenance.dependency_instances == {Measurement: InstanceKey(key="A")}
    assert copied.dependency_instances == {Measurement: InstanceKey(key="B")}


def test_dependencies_field_itself_is_completely_unaffected():
    record = ArtifactRecord(value=Measurement(value=1.0))

    record.advance(
        Measurement(value=2.0),
        origin=ArtifactOrigin.NODE,
    )

    assert record.dependencies == {}
    assert record.provenance.dependency_instances == {}
