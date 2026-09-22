"""
Slice 22D -- shared commit path `Session._commit(...)`;
`NodeSession.wrap()` unification
(`docs/refactor/session_snapshot_decision.md` section 6 "Unified
versioning and `ArtifactOrigin`"; `docs/refactor/architectural_invariants.md`
#10, #27, #28).

Prior to this slice, `NodeSession.wrap()` advanced a private, per-node
running `ArtifactProvenance` (`self._provenance`, Milestone O7 Slice O7b)
and constructed a brand-new `ArtifactRecord` on every firing. This slice
replaces that with `Session._commit(value, *, origin, producer=None)`: a
single, type-keyed operation both `NodeSession.wrap()` (this slice) and
the future `Session.feed()` (Slice 22E) route through, deriving the next
version from the repository's own current `ArtifactRecord` for that type
(invariant #28) instead of a private counter.

These tests exercise the wiring behaviorally, through the public
`Flow`/`Session` surface (`flow.session()`, `session.feed(...)`/`session.push()`,
`session.repository`), the same way
`tests/test_observability_o7b_provenance_version.py` already does --
no test here asserts on `NodeSession._provenance` directly (that
attribute no longer exists; see
`test_node_session_no_longer_has_a_private_provenance_field`).
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow():
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def test_node_session_wrap_uses_shared_commit_path():
    """
    `NodeSession.wrap(...)` no longer builds its own `ArtifactRecord`;
    it delegates to `Session._commit(...)`, which stores the record into
    `session.repository` directly. Observable proof: the record `.wrap()`
    produces (surfaced here via `.commit()`'s caller, exercised through `session.feed()`/`session.push()`)
    is retrievable from the repository afterward and carries the
    `ArtifactOrigin.NODE` origin and this firing's `NodeSession` as
    producer -- exactly the values `Session._commit` was called with.
    """
    from reed.execution.artifact_record import ArtifactOrigin

    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    record = session.repository.get_artifact_record(Estimate)
    assert record is not None
    assert record.value.value == 1
    assert record.provenance.origin is ArtifactOrigin.NODE
    assert record.provenance.producer is session.node_session(produce)


def test_repeated_firings_still_advance_the_same_record_in_place():
    """
    Repeated firings of the same Node must keep advancing the SAME
    `ArtifactRecord` object in the repository (Slice 22C's aliasing
    model, now actually reached via `.wrap()`) rather than constructing
    a fresh one each time -- the behavioral signature of `_commit`
    routing through `get_artifact_record(...)` + `.advance(...)` on a
    cache hit.
    """
    flow, produce = _make_flow()
    session = flow.session()

    session.feed(Measurement(1))
    session.push()
    first_record = session.repository.get_artifact_record(Estimate)
    assert first_record.version.number == 1
    assert first_record.value.value == 1

    session.feed(Measurement(2))
    session.push()
    second_record = session.repository.get_artifact_record(Estimate)

    # Same object, mutated in place -- not a new ArtifactRecord.
    assert second_record is first_record
    assert first_record.version.number == 2
    assert first_record.value.value == 2

    session.feed(Measurement(3))
    session.push()
    third_record = session.repository.get_artifact_record(Estimate)
    assert third_record is first_record
    assert first_record.version.number == 3
    assert first_record.value.value == 3


def test_first_commit_of_a_type_still_starts_at_artifact_version_initial():
    """
    The very first commit of a type -- the `_commit` branch where
    `get_artifact_record(...)` returns `None` -- must still produce
    `ArtifactVersion.initial()` (1), exactly what pre-22D `wrap()`
    produced from its own first `self._provenance.advance(...)` call.
    This is the SliceContract's own named risk
    (`stop_conditions`): verified here rather than assumed.
    """
    from reed.execution.artifact_record import ArtifactOrigin, ArtifactVersion

    flow, produce = _make_flow()
    session = flow.session()

    assert session.repository.get_artifact_record(Estimate) is None

    session.feed(Measurement(7))
    session.push()

    record = session.repository.get_artifact_record(Estimate)
    assert record is not None
    assert record.version == ArtifactVersion.initial()
    assert record.version.number == 1
    assert record.provenance.origin is ArtifactOrigin.NODE
    assert record.provenance.producer is session.node_session(produce)
    assert record.provenance.dependencies == {}


def test_node_session_no_longer_has_a_private_provenance_field():
    """
    Slice 22D drops `NodeSession`'s private `self._provenance` field
    entirely -- version and provenance are now read from the repository
    via `Session._commit(...)`, never from a private per-node counter.
    """
    flow, produce = _make_flow()
    session = flow.session()
    node_session = session.node_session(produce)

    assert not hasattr(node_session, "_provenance")
    assert "_provenance" not in vars(node_session)

    # And this holds after a real firing too, not just before one.
    session.feed(Measurement(1))
    session.push()
    assert not hasattr(node_session, "_provenance")
    assert "_provenance" not in vars(node_session)


def test_session_commit_advances_existing_record_in_place_and_returns_it():
    """
    Directly exercises `Session._commit(...)`'s own contract (not just
    through `NodeSession.wrap()`): a second `_commit` call for a type
    that already has a committed record advances that SAME object in
    place and returns it, rather than constructing a new one.
    """
    from reed.execution.artifact_record import ArtifactOrigin

    flow, _produce = _make_flow()
    session = flow.session()

    first = session._commit(Estimate(1), origin=ArtifactOrigin.EXTERNAL)
    assert first.version.number == 1

    second = session._commit(Estimate(2), origin=ArtifactOrigin.EXTERNAL)
    assert second is first
    assert first.version.number == 2
    assert first.value.value == 2
    assert session.repository.get_artifact_record(Estimate) is first
