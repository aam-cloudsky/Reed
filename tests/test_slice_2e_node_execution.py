"""
Focused tests for Slice 2E (NodeExecution firing pipeline: build
arguments, execute, wrap/commit ArtifactRecord, wire ctx.last_output).

These tests are additional to, and narrower than, this slice's two
required target contracts (`tests/test_target_architecture_contract.py`:
`test_run_instances_isolate_node_memory`,
`test_last_output_exposes_latest_committed_domain_value`). They isolate
each piece of the firing pipeline this slice adds:

    - `Run.publish(...)` for a stateless node (no NodeContext at all).
    - `NodeRuntime.wrap(...)` / `.commit(...)` committing into
      `run.repository`'s additive, domain-type-keyed ArtifactRecord
      storage (docs/parcel_boundary_decision.md, "Addendum: Slice 2E
      ArtifactRecord Commit Storage"), independent of `Depot`'s existing
      Parcel storage path.
    - `Run.publish(...)`'s explicit refusal to guess multi-node
      dispatch/routing when the published type matches zero or more than
      one registered FlowNode.

Multi-node graph propagation, TriggerPolicy-gated execution eligibility,
on_output dispatch, and firing-failure/rollback semantics are explicitly
out of scope for this slice (see `docs/parcel_boundary_decision.md`'s
addendum and the SliceContract's stop_conditions) and are not tested
here.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class OtherMeasurement:
    def __init__(self, value: int) -> None:
        self.value = value


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def test_publish_fires_the_matching_node_and_returns_its_output():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value * 2)

    flow = Flow()
    flow.add(estimate)
    run = flow.run()

    result = run.publish(Measurement(5))

    assert isinstance(result, Estimate)
    assert result.value == 10


def test_publish_commits_an_artifact_record_into_run_repository():
    from reed import Flow
    from reed.execution.artifact_record import ArtifactRecord, ArtifactVersion

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    run = flow.run()

    run.publish(Measurement(7))

    committed = run.repository.get_artifact_record(Estimate)
    assert isinstance(committed, ArtifactRecord)
    assert committed.value.value == 7
    assert committed.version == ArtifactVersion.initial()


def test_committed_artifact_record_storage_is_independent_of_parcel_storage():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    run = flow.run()

    run.publish(Measurement(3))

    # The additive ArtifactRecord path must not touch Depot's existing,
    # untouched Parcel storage.
    assert run.repository.get_parcel(Estimate) is None


def test_node_runtime_last_output_updates_after_publish():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    assert run.node_runtime(track).last_output is None

    run.publish(Measurement(4))

    assert run.node_runtime(track).last_output.value == 4


def test_publish_passes_node_context_when_node_declares_one():
    from reed import Flow, NodeContext

    seen_memory: list[TrackerMemory] = []

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        seen_memory.append(ctx.memory)
        ctx.memory.previous_confidence = measurement.value / 10
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    run.publish(Measurement(6))

    assert len(seen_memory) == 1
    assert seen_memory[0].previous_confidence == 0.6
    # Same memory object identity as the NodeRuntime's own memoized memory.
    assert run.node_runtime(track).memory is seen_memory[0]


def test_publish_raises_when_no_flow_node_consumes_the_published_type():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    run = flow.run()

    with pytest.raises(ValueError):
        run.publish(OtherMeasurement(1))


def test_publish_raises_when_more_than_one_flow_node_consumes_the_published_type():
    from reed import Flow

    def estimate_a(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def estimate_b(measurement: Measurement) -> OtherMeasurement:
        return OtherMeasurement(measurement.value)

    flow = Flow()
    flow.add(estimate_a)
    flow.add(estimate_b)
    run = flow.run()

    with pytest.raises(ValueError):
        run.publish(Measurement(1))
