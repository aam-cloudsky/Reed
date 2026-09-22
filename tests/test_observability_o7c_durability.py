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


from reed.observability.instrument import Instrument, InstrumentKind


class InstrumentA(Instrument[int]):
    kind = InstrumentKind.GAUGE
    unit = "1"


class InstrumentB(Instrument[int]):
    kind = InstrumentKind.GAUGE
    unit = "1"


class InstrumentC(Instrument[int]):
    kind = InstrumentKind.GAUGE
    unit = "1"


def _make_flow_with_multi_record_node():
    from reed import Flow, NodeContext

    def produce(
        ctx: NodeContext[None, Estimate], measurement: Measurement
    ) -> Estimate:
        ctx.record(InstrumentA, 1)
        ctx.record(InstrumentB, 2)
        ctx.record(InstrumentC, 3)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow, produce


def test_multiple_recordings_in_one_firing_fsync_once(tmp_path, monkeypatch):
    flow, produce = _make_flow_with_multi_record_node()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def counting_fsync(fd):
        fsync_calls["n"] += 1
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)

    session.feed(Measurement(1))
    session.push()

    # Three ctx.record(...) calls in one firing must flush as one batch at
    # the NodeExecution durability boundary -- not once per call: that is
    # 1 fsync. The remaining 3 are Provenance events (out of this slice's
    # scope -- O7c is about ctx.record()'s hot path specifically, not
    # Provenance, which is one fsync per event already, not a repeated
    # hot-path call): feed()'s own "generated" event for the externally
    # fed Measurement, the "used" event produce's firing now emits for
    # that already-committed Measurement, and the "generated" event for
    # produce's own committed Estimate output (Slice 22E;
    # session_snapshot_decision.md section 1, point 2 -- a fed root
    # value now becomes a provenance-tracked record like any other,
    # where the old publish() never committed or emitted anything for
    # the root value itself).
    assert fsync_calls["n"] == 4

    # All three rows must still have been written.
    from reed.observability.replay import load_recordings

    run_dir = root / "runs" / session.execution_id
    rows = load_recordings(run_dir)
    assert len(rows) == 3
    assert {row["name"] for row in rows} == {
        InstrumentA.instrument_name(),
        InstrumentB.instrument_name(),
        InstrumentC.instrument_name(),
    }


def test_recordings_are_durable_after_a_successful_firing(tmp_path):
    from reed.observability.replay import load_recordings

    flow, produce = _make_flow_with_multi_record_node()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    session.feed(Measurement(1))
    session.push()

    run_dir = root / "runs" / session.execution_id
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
    from reed.observability.instrument import Instrument, InstrumentKind
    from reed.observability.replay import load_recordings

    class Flag(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "1"

    def failing_node(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Flag, 1)
        raise RuntimeError("boom")

    flow = Flow()
    flow.add(failing_node)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    try:
        session.feed(Measurement(1))
        session.push()
    except RuntimeError:
        pass

    run_dir = root / "runs" / session.execution_id
    rows = load_recordings(run_dir)
    assert len(rows) == 1
    assert rows[0]["name"] == Flag.instrument_name()


def test_no_fsync_when_no_recordings_are_made_in_a_firing(tmp_path, monkeypatch):
    from reed import Flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))

    fsync_calls = {"n": 0}
    real_fsync = os.fsync

    def counting_fsync(fd):
        fsync_calls["n"] += 1
        return real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)

    session.feed(Measurement(1))
    session.push()

    # No ctx.record(...) calls were made, so no Recording batch is
    # flushed -- the remaining fsyncs are Provenance events (out of this
    # slice's scope, see above): feed()'s own "generated" event for the
    # externally fed Measurement, the "used" event produce's firing now
    # emits for that already-committed Measurement, and the "generated"
    # event for produce's own committed Estimate output (Slice 22E).
    assert fsync_calls["n"] == 3
