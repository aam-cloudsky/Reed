"""
Focused tests for Slice 2F (on_output dispatch after commit: sync/async
callback support and callback-failure isolation via
`session.callback_failures`).

These tests are additional to, and narrower than, this slice's three
required target contracts
(`tests/test_target_architecture_contract.py`:
`test_on_output_runs_after_commit_and_receives_domain_value`,
`test_async_on_output_is_supported_after_commit`,
`test_callback_failure_does_not_undo_committed_output`). They isolate
each piece of the dispatch step this slice adds to `Session.push()`:

    - a node with no declared `on_output` still publishes/commits
      normally (no dispatch attempted, no error);
    - a synchronous `on_output` runs inline, immediately after commit,
      and receives the domain value (not the `ArtifactRecord`);
    - an async `on_output`'s coroutine is queued rather than awaited
      inside `push()`, and is only driven to completion by an
      explicit `session.wait_for_callbacks()` call;
    - a synchronous callback failure is isolated into
      `session.callback_failures` without affecting the committed record;
    - an async callback failure raised during `wait_for_callbacks()` is
      isolated into `session.callback_failures` the same way;
    - `ArtifactRepository.get(domain_type)` is a thin, additive alias for
      `ArtifactRepository.get_artifact_record(domain_type)`.

Multi-node graph propagation, TriggerPolicy-gated execution eligibility,
and stateful-firing serialization remain out of scope for this slice (see
the SliceContract's stop_conditions) and are not tested here.
"""

from __future__ import annotations

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_publish_with_no_on_output_declared_still_commits_normally():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    session = flow.session()

    snapshot = session.invoke(Measurement(9))
    result = snapshot[Estimate]

    assert isinstance(result, Estimate)
    assert result.value == 9
    assert session.repository.get(Estimate).value.value == 9
    assert session.callback_failures == []


def test_sync_on_output_runs_inline_and_receives_domain_value():
    from reed import Flow

    observed: list[Estimate] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        observed.append(value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    session = flow.session()

    session.feed(Measurement(4))
    session.push()

    # No wait_for_callbacks() needed -- the sync callback already ran
    # inline, before push() returned.
    assert len(observed) == 1
    assert observed[0] is session.repository.get(Estimate).value
    assert session.callback_failures == []


def test_async_on_output_coroutine_is_not_awaited_before_wait_for_callbacks():
    from reed import Flow

    observed: list[int] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    async def on_output(value: Estimate) -> None:
        observed.append(value.value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    session = flow.session()

    session.feed(Measurement(6))
    session.push()

    # push() itself stays synchronous; the coroutine has not run
    # yet.
    assert observed == []

    session.wait_for_callbacks()

    assert observed == [6]
    assert session.callback_failures == []


def test_sync_callback_failure_is_isolated_and_does_not_undo_commit():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        raise RuntimeError("boom")

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    session = flow.session()

    snapshot = session.invoke(Measurement(11))
    result = snapshot[Estimate]

    assert result.value == 11
    assert session.repository.get(Estimate).value.value == 11
    assert len(session.callback_failures) == 1
    assert isinstance(session.callback_failures[0], RuntimeError)


def test_async_callback_failure_is_isolated_via_wait_for_callbacks():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    async def on_output(value: Estimate) -> None:
        raise RuntimeError("async boom")

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    session = flow.session()

    session.feed(Measurement(13))
    session.push()
    assert session.callback_failures == []  # not yet observed -- not awaited

    session.wait_for_callbacks()

    assert session.repository.get(Estimate).value.value == 13
    assert len(session.callback_failures) == 1
    assert isinstance(session.callback_failures[0], RuntimeError)


def test_wait_for_callbacks_is_a_no_op_when_nothing_is_pending():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    session = flow.session()

    session.feed(Measurement(1))
    session.push()

    # Should not raise even though no async on_output was ever declared.
    session.wait_for_callbacks()

    assert session.callback_failures == []


def test_artifact_repository_get_is_an_additive_alias_for_get_artifact_record():
    from reed.synchronization.artifact_repository import ArtifactRepository
    from reed.transportation.bus import Bus
    from reed.execution.artifact_record import ArtifactRecord

    depot = ArtifactRepository(bus=Bus.create())
    record = ArtifactRecord(value=Estimate(42))

    depot.set_artifact_record(record)

    assert depot.get(Estimate) is depot.get_artifact_record(Estimate)
    assert depot.get(Estimate).value.value == 42
    assert depot.get(Measurement) is None
