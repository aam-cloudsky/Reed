"""
Milestone O6, Slice O6c -- `reed query <flow_id>`: cross-Execution
aggregation over recordings.csv via a documented glob pattern (design
record §27).
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


from reed.observability.instrument import Instrument, InstrumentKind


class Speed(Instrument[int]):
    kind = InstrumentKind.GAUGE
    unit = "m/s"


def _make_flow():
    from reed import Flow, NodeContext

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    return flow


def test_query_recordings_aggregates_across_separate_executions(tmp_path):
    from reed.observability.query import query_recordings

    flow = _make_flow()
    root = tmp_path / ".reed"

    first_session = flow.session(storage_root=str(root))
    first_session.feed(Measurement(1))
    first_session.push()

    second_session = flow.session(storage_root=str(root))
    second_session.feed(Measurement(2))
    second_session.push()

    rows = query_recordings(root, flow.flow_id)

    assert len(rows) == 2
    assert {row["execution_id"] for row in rows} == {
        first_session.execution_id,
        second_session.execution_id,
    }
    assert {row["value"] for row in rows} == {"1", "2"}


def test_query_recordings_filters_by_flow_id():
    from reed import Flow, NodeContext
    from reed.observability.query import query_recordings

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    def other_produce(
        ctx: NodeContext[None, Estimate], measurement: Measurement
    ) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        from pathlib import Path

        root = Path(tmp) / ".reed"

        flow_a = Flow()
        flow_a.add(produce)
        session_a = flow_a.session(storage_root=str(root))
        session_a.feed(Measurement(1))
        session_a.push()

        flow_b = Flow()
        flow_b.add(other_produce)
        session_b = flow_b.session(storage_root=str(root))
        session_b.feed(Measurement(2))
        session_b.push()

        rows = query_recordings(root, flow_a.flow_id)

        assert len(rows) == 1
        assert rows[0]["execution_id"] == session_a.execution_id


def test_recordings_glob_pattern_matches_documented_shape(tmp_path):
    from reed.observability.query import recordings_glob_pattern

    pattern = recordings_glob_pattern(tmp_path / ".reed")
    assert pattern.endswith(str(tmp_path / ".reed" / "runs" / "*" / "recordings.csv"))


def test_query_recordings_returns_empty_for_unknown_flow_id(tmp_path):
    from reed.observability.query import query_recordings

    flow = _make_flow()
    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    rows = query_recordings(root, "nonexistent-flow-id")
    assert rows == []
