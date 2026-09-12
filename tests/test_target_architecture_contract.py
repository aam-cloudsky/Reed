from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


class OtherEstimate:
    pass


class RawImage:
    pass


class MaskedImage:
    pass


class EnhancedImage:
    pass


@dataclass
class TrackerMemory:
    previous_confidence: float | None = None


def test_flow_add_registers_callable_and_returns_flownode():
    from reed import Flow
    from reed.flow import FlowNode

    def produce() -> Measurement:
        return Measurement(1)

    flow = Flow()
    flow_node = flow.add(produce)

    assert isinstance(flow_node, FlowNode)
    assert flow_node.definition.function is produce
    assert flow_node.produced_artifact.domain_type is Measurement


def test_flow_add_uses_keyword_only_trigger_policy_and_on_output():
    from reed import Flow, TriggerPolicy

    def produce() -> Estimate:
        return Estimate(1)

    def on_output(value: Estimate) -> None:
        assert isinstance(value, Estimate)

    flow = Flow()
    flow_node = flow.add(
        produce,
        trigger_policy=TriggerPolicy.ALL_INPUTS_CHANGED,
        on_output=on_output,
    )

    assert flow_node.trigger_policy is TriggerPolicy.ALL_INPUTS_CHANGED
    assert flow_node.on_output is on_output


def test_flow_add_rejects_positional_configuration_ambiguity():
    from reed import Flow, TriggerPolicy

    def produce() -> Estimate:
        return Estimate(1)

    def on_output(value: Estimate) -> None:
        pass

    flow = Flow()

    with pytest.raises(TypeError):
        flow.add(produce, on_output, TriggerPolicy.ALL_INPUTS_CHANGED)


def test_node_signature_uses_domain_types_not_artifact_records():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow_node = flow.add(estimate)

    assert flow_node.consumed_artifacts[0].domain_type is Measurement
    assert flow_node.produced_artifact.domain_type is Estimate


def test_node_context_is_injected_and_not_registered_as_input_port():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow_node = flow.add(track)

    assert [artifact.domain_type for artifact in flow_node.consumed_artifacts] == [
        Measurement
    ]
    assert flow_node.context.memory_type is TrackerMemory
    assert flow_node.context.output_type is Estimate


def test_node_context_output_type_must_match_return_type():
    from reed import Flow, NodeContext

    def invalid(
        ctx: NodeContext[TrackerMemory, OtherEstimate],
        measurement: Measurement,
    ) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()

    with pytest.raises(Exception, match="NodeContext.*return"):
        flow.add(invalid)


def test_duplicate_output_domain_type_is_rejected_in_one_flow():
    from reed import Flow

    def first(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def second(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value + 1)

    flow = Flow()
    flow.add(first)

    with pytest.raises(Exception, match="producer|produce|Estimate"):
        flow.add(second)


def test_self_flow_signature_is_rejected():
    from reed import Flow

    def invalid(measurement: Measurement) -> Measurement:
        return measurement

    flow = Flow()

    with pytest.raises(Exception, match="self|same|Measurement"):
        flow.add(invalid)


def test_parallel_safe_branching_uses_distinct_output_artifact_types():
    from reed import Flow

    def mask(image: RawImage) -> MaskedImage:
        return MaskedImage()

    def enhance(image: RawImage) -> EnhancedImage:
        return EnhancedImage()

    flow = Flow()
    mask_node = flow.add(mask)
    enhance_node = flow.add(enhance)

    assert mask_node.produced_artifact.domain_type is MaskedImage
    assert enhance_node.produced_artifact.domain_type is EnhancedImage


def test_run_instances_isolate_node_memory():
    from reed import Flow, NodeContext

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        ctx.memory.previous_confidence = measurement.value / 10
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)

    first_run = flow.run()
    second_run = flow.run()

    first_run.publish(Measurement(1))
    second_run.publish(Measurement(8))

    assert first_run.node_runtime(track).context.memory.previous_confidence == 0.1
    assert second_run.node_runtime(track).context.memory.previous_confidence == 0.8


def test_last_output_exposes_latest_committed_domain_value():
    from reed import Flow, NodeContext

    seen_previous: list[Estimate | None] = []

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        seen_previous.append(ctx.last_output)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track)
    run = flow.run()

    run.publish(Measurement(1))
    run.publish(Measurement(2))

    assert seen_previous[0] is None
    assert isinstance(seen_previous[1], Estimate)
    assert seen_previous[1].value == 1


def test_on_output_runs_after_commit_and_receives_domain_value():
    from reed import Flow

    observed: list[Estimate] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        observed.append(value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    run = flow.run()

    run.publish(Measurement(3))

    committed = run.repository.get(Estimate)
    assert observed == [committed.value]
    assert isinstance(observed[0], Estimate)
    assert observed[0].value == 3


def test_async_on_output_is_supported_after_commit():
    from reed import Flow

    observed: list[int] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    async def on_output(value: Estimate) -> None:
        await asyncio.sleep(0)
        observed.append(value.value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    run = flow.run()

    run.publish(Measurement(5))
    run.wait_for_callbacks()

    assert observed == [5]


def test_callback_failure_does_not_undo_committed_output():
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        raise RuntimeError("external observer failed")

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    run = flow.run()

    run.publish(Measurement(7))

    assert run.repository.get(Estimate).value.value == 7
    assert run.callback_failures


def test_stateful_node_runtime_firings_are_serialized():
    from reed import Flow, NodeContext, TriggerPolicy

    active = 0
    max_active = 0

    def track(
        ctx: NodeContext[TrackerMemory, Estimate],
        measurement: Measurement,
    ) -> Estimate:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        active -= 1
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(track, trigger_policy=TriggerPolicy.ANY_INPUT_CHANGED)
    run = flow.run()

    run.publish_many([Measurement(1), Measurement(2)])

    assert max_active == 1

