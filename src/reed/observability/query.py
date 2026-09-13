"""
`reed query <flow_id>` (Milestone O6, Slice O6c).

Section 16.1's whole reason for `flow_id`/`node_id` stability across separate process
executions (Section 18, resolved at Slice O1a) is cross-Execution aggregation: a documented
glob pattern over every past Execution's `recordings.csv`, filtered to one logical Flow.

The canonical pattern (design record Section 16.4/17.1), which this module documents and
provides a pure-Python reference implementation of, is a glob over
`<storage_root>/runs/*/recordings.csv` filtered by the `flow_id` column (recordings.csv is
partitioned by `execution_id`, i.e. one file per Run -- not by `flow_id` -- so filtering by
`flow_id` is always a column filter across many files, never a directory selector):

    DuckDB:
        SELECT * FROM read_csv_auto('.reed/runs/*/recordings.csv') WHERE flow_id = '<flow_id>'

    Polars:
        pl.scan_csv(".reed/runs/*/recordings.csv").filter(pl.col("flow_id") == flow_id)

This module's `query_recordings(...)` is a pure-Python reference implementation of the same
pattern (glob + `csv.DictReader` + filter) with no DuckDB/Polars dependency -- suitable for
small local exploration and for this repository's own tests, not a replacement for either
tool at any real Run volume. A user with many/large Executions should reach for DuckDB or
Polars directly using the query strings above, not this function.

**Flow-shape-drift caveat (Section 17.2, explicitly not solved here, only documented):**
aggregating many Executions under one `flow_id` implicitly assumes those Executions ran a
structurally comparable Flow. If a Node's Instrument `unit` changes, or a Node is added or
removed, between two Executions that still share a `flow_id` (because the code changed in a
way `flow_id`'s registration-order-sensitive hash did not happen to change -- Section 18.4's
known accepted limitation), a cross-run query can silently mix incompatible series. This is
left as a user judgment call, exactly as Section 17.2 states -- `query_recordings(...)` does
not attempt to detect or warn about it.
"""

from __future__ import annotations

import csv
import glob
from pathlib import Path


def recordings_glob_pattern(storage_root: Path) -> str:
    """
    The canonical glob pattern (Section 16.4) for every Execution's
    `recordings.csv` under `storage_root`, before any `flow_id` filtering.
    """
    return str(Path(storage_root) / "runs" / "*" / "recordings.csv")


def query_recordings(storage_root: Path, flow_id: str) -> list[dict[str, str]]:
    """
    Reference implementation of the canonical cross-Execution query
    pattern: glob every `recordings.csv` under `storage_root`, read each
    back, and keep only rows whose `flow_id` column matches `flow_id`.

    Rows are returned in no particular cross-file order beyond each file's
    own row order and `glob.glob`'s filesystem-dependent file order --
    a caller that needs a specific total order should sort the result by
    `execution_id`/`execution_seq` itself (both are columns on every row).
    """
    matched: list[dict[str, str]] = []
    for path in glob.glob(recordings_glob_pattern(storage_root)):
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["flow_id"] == flow_id:
                    matched.append(row)
    return matched
