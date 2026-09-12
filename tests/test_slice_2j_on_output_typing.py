"""
Focused tests for Slice 2J (on_output type-level fix: `Flow.add` becomes
generic over the node function's declared output type, so a plainly
domain-typed callback type-checks under strict Pyright without a
contravariance error).

This is a type-annotation-only change: `Flow.add`'s `function` parameter
becomes `Callable[..., OutputT]` and `on_output` becomes
`Callable[[OutputT], object] | None`, and `FlowNode.on_output`'s stored
field becomes `Callable[[Any], object] | None` (an internal-storage
escape hatch, since `FlowNode` itself stays non-generic). No runtime
dispatch, ordering, or exception-handling behavior changes at all --
these tests exist to prove exactly that: on_output still fires
post-commit with the correct domain value, identically to Slice 2F's
existing coverage. The primary verification for this slice is a
`pyright` invocation (recorded in the implementation report), not new
runtime assertions -- these are sanity checks that the annotation
change did not alter behavior.
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_on_output_still_runs_after_commit_and_receives_domain_value():
    """Runtime-behavior-preservation: same shape as Slice 2F's
    `test_sync_on_output_runs_inline_and_receives_domain_value`."""
    from reed import Flow

    observed: list[Estimate] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    def on_output(value: Estimate) -> None:
        observed.append(value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    run = flow.run()

    result = run.publish(Measurement(9))

    assert isinstance(result, Estimate)
    assert result.value == 9
    assert len(observed) == 1
    assert observed[0] is run.repository.get(Estimate).value
    assert run.callback_failures == []


def test_publish_with_no_on_output_declared_still_commits_normally():
    """Runtime-behavior-preservation: same shape as Slice 2F's test of
    the same name -- `on_output` remains optional at the call site."""
    from reed import Flow

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(estimate)
    run = flow.run()

    result = run.publish(Measurement(3))

    assert isinstance(result, Estimate)
    assert result.value == 3
    assert run.callback_failures == []


def test_async_on_output_still_dispatches_via_wait_for_callbacks():
    """Runtime-behavior-preservation: same shape as Slice 2F's async
    dispatch test -- an async on_output is still only driven by an
    explicit `wait_for_callbacks()` call, unaffected by the typing
    change."""
    from reed import Flow

    observed: list[int] = []

    def estimate(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    async def on_output(value: Estimate) -> None:
        observed.append(value.value)

    flow = Flow()
    flow.add(estimate, on_output=on_output)
    run = flow.run()

    run.publish(Measurement(6))
    assert observed == []

    run.wait_for_callbacks()

    assert observed == [6]
    assert run.callback_failures == []


def test_flow_add_accepts_a_domain_typed_callback_with_a_different_domain_type():
    """A second, distinct domain output type still works end to end --
    guards against any accidental single-type hard-coding in the
    generic signature."""
    from reed import Flow

    class Reading:
        def __init__(self, value: int) -> None:
            self.value = value

    observed: list[Reading] = []

    def sense(measurement: Measurement) -> Reading:
        return Reading(measurement.value * 2)

    def on_output(value: Reading) -> None:
        observed.append(value)

    flow = Flow()
    flow.add(sense, on_output=on_output)
    run = flow.run()

    run.publish(Measurement(5))

    assert len(observed) == 1
    assert observed[0].value == 10
