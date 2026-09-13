"""
Milestone O6, Slice O6b -- `reed describe`: introspect declared Instruments
with no execution required (design record §26).
"""

from __future__ import annotations


class Measurement:
    def __init__(self, value: int) -> None:
        self.value = value


class Estimate:
    def __init__(self, value: int) -> None:
        self.value = value


def test_describe_flow_lists_declared_instruments_with_no_execution():
    from reed import Flow
    from reed.observability.describe import describe_flow
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce, instruments=[speed])
    # No run() / publish() call at all -- describe works from the bare Flow.

    table = describe_flow(flow)

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == "speed"
    assert table.columns[2]._cells[0] == "gauge"


def test_describe_flow_lists_nodes_with_no_declared_instruments():
    from reed import Flow
    from reed.observability.describe import describe_flow

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce)

    table = describe_flow(flow)

    # O7f: a blank cell here would be indistinguishable from "this Node
    # truly has no Instrument activity" -- but a Node with no *declared*
    # Instruments may still record lazy-mode Recordings at runtime, which
    # static describe() cannot know in advance. LAZY_CAPABLE_LABEL makes
    # that distinction explicit instead of rendering an empty string.
    from reed.observability.describe import LAZY_CAPABLE_LABEL

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == LAZY_CAPABLE_LABEL


def test_describe_instruments_manifest_reads_past_run_manifest(tmp_path):
    from reed import Flow
    from reed.observability.describe import describe_instruments_manifest
    from reed.observability.instrument import Instrument

    speed = Instrument(name="speed", kind="gauge", unit="m/s")

    def produce(measurement: Measurement) -> Estimate:
        return Estimate(measurement.value)

    flow = Flow()
    flow.add(produce, instruments=[speed])

    root = tmp_path / ".reed"
    run = flow.run(storage_root=str(root))
    run.publish(Measurement(1))

    manifest_path = root / "flows" / flow.flow_id / "instruments.json"
    table = describe_instruments_manifest(manifest_path)

    assert table.row_count == 1
    assert table.columns[1]._cells[0] == "speed"
