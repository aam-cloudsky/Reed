"""
Milestone O7, Slice O7c -- Recording durability boundary is NodeExecution
exit, not per-`ctx.record()` fsync (docs/observability_goals.md Section
5; docs/observability_non_goals.md Section 5; architectural invariants
#20/#21/#26).

Regression for a confirmed contract violation: the pre-fix
`CSVRecordingStore.append(...)` flushed and fsynced on every single
`ctx.record(...)` call. `observability_non_goals.md` Section 5 explicitly
forbids this exact "fix" ("Do not 'fix' this by adding an fsync per
ctx.record() call... That destroys the hot-path latency the synchronous,
non-blocking call is designed to protect") -- so the previous
implementation contradicted its own authoritative documents, which had
incorrectly rationalized it in the design record as "exceeding, not
violating" the contract.

These tests observe `fsync` call counts via monkeypatching `os.fsync`,
since NodeExecution-scoped batching is otherwise invisible from the CSV
file's final contents alone (the rows are identical either way).
"""

from __future__ import annotations

import os


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def _make_flow_with_multi_record_node():
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument

    a = Instrument(name="a", kind="gauge", unit="1")
    b = Instrument(name="b", kind="gauge", unit="1")
    c = Instrument(name="c", kind="gauge", unit="1")

    def produce(
        ctx: NodeContext[None, Estimate], measurement: Measurement
    ) -> Estimate:
        ctx.record(a, 1)
        ctx.record(b, 2)
        ctx.record(c, 3)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce, instruments=[a, b, c])
    return flow, produce


def test_multiple_recordings_in_one_firing_fsync_once(tmp_path, monkeypatch):
    flow, produce = _make_flow_with_multi_record_node()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def counting_fsync(fd):
        fsync_calls["n"] += 1
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)

    run.publish(Measurement(1))

    # Three ctx.record(...) calls in one firing must flush as one batch at
    # the NodeExecution durability boundary -- not once per call. The
    # remaining fsync is the "generated" provenance event this firing's
    # own committed output triggers (out of this slice's scope -- O7c is
    # about ctx.record()'s hot path specifically, not Provenance, which
    # is one event per firing already, not a repeated hot-path call).
    assert fsync_calls["n"] == 2

    # All three rows must still have been written.
    from reed.observability.replay import load_recordings

    run_dir = root / "runs" / run.execution_id
    rows = load_recordings(run_dir)
    assert len(rows) == 3
    assert {row["name"] for row in rows} == {"a", "b", "c"}


def test_recordings_are_durable_after_a_successful_firing(tmp_path):
    from reed.observability.replay import load_recordings

    flow, produce = _make_flow_with_multi_record_node()
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    run.publish(Measurement(1))

    run_dir = root / "runs" / run.execution_id
    rows = load_recordings(run_dir)
    assert len(rows) == 3


def test_recordings_flush_even_when_the_node_raises(tmp_path):
    """
    The durability boundary is "NodeExecution exits -- normally,
    exceptionally, or through cancellation" (observability_goals.md
    Section 5). A Recording accepted before the Node raises must still
    be flushed to disk.
    """
    from reed import Flow, NodeContext
    from reed.observability.instrument import Instrument
    from reed.observability.replay import load_recordings

    flag = Instrument(name="flag", kind="gauge", unit="1")

    def failing_node(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(flag, 1)
        raise RuntimeError("boom")

    flow = Flow()
    flow.add(failing_node, instruments=[flag])
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    try:
        run.publish(Measurement(1))
    except RuntimeError:
        pass

    run_dir = root / "runs" / run.execution_id
    rows = load_recordings(run_dir)
    assert len(rows) == 1
    assert rows[0]["name"] == "flag"


def test_no_fsync_when_no_recordings_are_made_in_a_firing(tmp_path, monkeypatch):
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def counting_fsync(fd):
        fsync_calls["n"] += 1
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)

    run.publish(Measurement(1))

    # No ctx.record(...) calls were made, so no Recording batch is
    # flushed -- the one remaining fsync is this firing's own "generated"
    # provenance event (out of this slice's scope, see above).
    assert fsync_calls["n"] == 1
