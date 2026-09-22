"""
Milestone O6, Slice O6b -- `reed describe`; redesigned at Milestone O7,
Slice O7i for dynamically-discovered Instruments (design record §26, §34).
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_describe_flow_reports_nodes_with_no_instrument_column():
    """
    O7i: prospective Instrument declaration no longer exists, and
    describe_flow is a purely structural, composition-plane report --
    it lists Nodes only, with no Instrument column at all (an Instrument
    binding does not exist until some real Session discovers it).
    """
    from reed import Flow
    from reed.observability.describe import describe_flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    # No session() / publish() call at all -- describe works from the bare Flow.

    table = describe_flow(flow)

    assert table.row_count == 1
    assert len(table.columns) == 1
    assert table.columns[0]._cells[0] == flow.flow_nodes[0].node_id


def test_describe_instruments_manifest_reads_past_session_manifest(tmp_path):
    from reed import Flow, NodeContext
    from reed.observability.describe import describe_instruments_manifest
    from reed.observability.instrument import Instrument, InstrumentKind

    class Speed(Instrument[int]):
        kind = InstrumentKind.GAUGE
        unit = "m/s"

    def produce(ctx: NodeContext[None, Estimate], measurement: Measurement) -> Estimate:
        ctx.record(Speed, measurement.value)
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    table = describe_instruments_manifest(manifest_path)

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == Speed.instrument_name()
    assert table.columns[2]._cells[0] == "gauge"


def test_describe_instruments_manifest_has_no_row_for_a_node_that_never_recorded(
    tmp_path,
):
    """
    A Node that has never called ctx.record(...) in any Session of this Flow
    has nothing to report and no static declaration to fall back on --
    it simply does not appear in the manifest at all (O7i: there is no
    more "declared but never recorded" state to distinguish).
    """
    from reed import Flow
    from reed.observability.describe import describe_instruments_manifest

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    root = tmp_path / ".reed"
    session = flow.session(storage_root=str(root))
    session.feed(Measurement(1))
    session.push()

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    if not manifest_path.exists():
        # Nothing was ever recorded, so instruments.json was never
        # created at all -- also a valid, honest outcome.
        return

    table = describe_instruments_manifest(manifest_path)
    assert table.row_count == 0
