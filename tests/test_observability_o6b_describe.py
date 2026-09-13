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


def test_describe_flow_reports_discovery_is_runtime_only():
    """
    O7i: prospective Instrument declaration no longer exists -- every
    Node's Instrument column reads DISCOVERED_AT_RUNTIME_LABEL uniformly,
    whether or not it will ever call ctx.record(...). describe_flow
    still enumerates every Node in the Flow with no execution required.
    """
    from reed import Flow
    from reed.observability.describe import DISCOVERED_AT_RUNTIME_LABEL, describe_flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)
    # No run() / publish() call at all -- describe works from the bare Flow.

    table = describe_flow(flow)

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == DISCOVERED_AT_RUNTIME_LABEL


def test_describe_instruments_manifest_reads_past_run_manifest(tmp_path):
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
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    table = describe_instruments_manifest(manifest_path)

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == Speed.instrument_name()
    assert table.columns[2]._cells[0] == "gauge"


def test_describe_instruments_manifest_has_no_row_for_a_node_that_never_recorded(
    tmp_path,
):
    """
    A Node that has never called ctx.record(...) in any Run of this Flow
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
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    if not manifest_path.exists():
        # Nothing was ever recorded, so instruments.json was never
        # created at all -- also a valid, honest outcome.
        return

    table = describe_instruments_manifest(manifest_path)
    assert table.row_count == 0
