from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from reed.activation.role import Role
from reed.activation.schema import RepositoryAdapterSchemaBuilder
from reed.synchronization.artifact_repository_messages import (
    ArtifactRepositoryRegistry,
    ArtifactRepositorySet,
)
from reed.synchronization.parcel.parcel import Parcel
from reed.synchronization.parcel.provenance import ParcelVersion
from reed.synchronization.validity.dependency_registry import (
    DependencyRegistry,
    DuplicateProducerError,
)
from reed.synchronization.validity.repository_adapter_sentinel import (
    RepositoryAdapterSentinel,
)
from reed.transportation.protocol.message_context import MessageContext
from reed.transportation.publisher_manager import PublisherID


@dataclass
class SourceParcel(Parcel):
    value: int


@dataclass
class DerivedParcel(Parcel):
    value: int


@dataclass
class OtherDerivedParcel(Parcel):
    value: int


class ProducerA:
    pass


class ProducerB:
    pass


class Consumer:
    pass


def message_context(publisher_type: type) -> MessageContext:
    return MessageContext(
        publisher_type=publisher_type,
        from_id=PublisherID(id(publisher_type) % 100000),
    )


def test_dependency_registry_rejects_duplicate_producers_for_same_parcel_type():
    registry = DependencyRegistry()

    registry.register_module(
        ProducerA,
        {Role.PRODUCED: {DerivedParcel}},
    )

    with pytest.raises(DuplicateProducerError, match="Only one producer"):
        registry.register_module(
            ProducerB,
            {Role.PRODUCED: {DerivedParcel}},
        )


def test_dependency_registry_exposes_upstream_and_downstream_modules():
    registry = DependencyRegistry()

    registry.register_module(
        ProducerA,
        {Role.PRODUCED: {SourceParcel}},
    )
    registry.register_module(
        Consumer,
        {
            Role.CONSUMED: {SourceParcel},
            Role.PRODUCED: {DerivedParcel},
        },
    )

    assert registry.upstream_modules(Consumer) == {ProducerA}
    assert registry.downstream_modules(ProducerA) == {Consumer}
    assert registry.dependency_edges() == {(ProducerA, Consumer)}


def test_schema_builder_extracts_parcel_roles_and_produced_dependencies():
    @dataclass(eq=False)
    class RuntimeSchema(RepositoryAdapterSchemaBuilder):
        source: SourceParcel = field(
            default=None,
            metadata={"role": Role.CONSUMED},
        )
        derived: DerivedParcel = field(
            default=None,
            metadata={"role": Role.PRODUCED},
        )

    schema = RuntimeSchema.schema()

    assert schema.types_by_role[Role.CONSUMED] == {SourceParcel}
    assert schema.types_by_role[Role.PRODUCED] == {DerivedParcel}
    assert schema.descriptor(SourceParcel).field_name == "source"
    assert schema.descriptor(DerivedParcel).field_name == "derived"
    assert schema.descriptor(DerivedParcel).depends_on == {SourceParcel}


def test_parcel_record_origin_advances_version_and_records_dependencies():
    source = SourceParcel(1)
    source.record_origin(node_id=None)

    derived = DerivedParcel(2)
    derived.record_origin(
        node_id=None,
        dependencies={SourceParcel: source.version},
    )

    assert source.version == ParcelVersion.initial()
    assert derived.version == ParcelVersion.initial()
    assert derived.dependencies == {SourceParcel: source.version}


def test_parcel_record_origin_inherits_previous_version_before_advancing():
    previous = DerivedParcel(1)
    previous.record_origin(node_id=None)

    current = DerivedParcel(2)
    current.record_origin(previous=previous, node_id=None)

    assert current.version == previous.version.next()


def test_sentinel_marks_registered_produced_parcels_invalid_then_valid_on_set():
    sentinel = RepositoryAdapterSentinel()
    context = message_context(ProducerA)

    sentinel.register(
        ArtifactRepositoryRegistry(
            outpost_type=ProducerA,
            parcels_by_role={Role.PRODUCED: {DerivedParcel}},
        ),
        context,
    )

    transition = sentinel.verify_validity(
        ArtifactRepositorySet(pallet={DerivedParcel: DerivedParcel(1)}),
        context,
    )

    assert transition.became_valid == {DerivedParcel}
    assert transition.became_invalid == set()
    assert transition.after[DerivedParcel] is True
