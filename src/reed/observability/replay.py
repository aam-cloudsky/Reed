"""
Post-hoc replay of a past Execution (Milestone O5, Slice O5c, optional).

Extends the O5b terminal renderer to also read `recordings.csv`/`provenance.csv` (Milestone
O3) for a Session whose process has already exited -- strictly more capable than the old
Bus-based system, which could only show live request/reply traffic (design record Section
8's "it can show provenance and recordings, not only Bus request/reply pairs").

This is read-only: it never reconstructs a live `Session`/`ExecutionTrace`, only a static
snapshot table built directly from the two CSV files a past Execution left behind under
`<storage_root>/runs/<execution_id>/`. It requires `storage_root` to have been configured for
that Execution (Milestone O3's opt-in) -- there is nothing to replay for an in-memory-only
Session, and this module raises `FileNotFoundError` rather than silently rendering an empty
table in that case, so a caller does not mistake "no storage was configured" for "this
Execution recorded nothing."
"""

from __future__ import annotations

import csv
from pathlib import Path

from rich.console import Console
from rich.table import Table


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist -- was storage_root configured for this "
            "execution_id, and did the Session actually fire any Nodes?"
        )
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_recordings(run_dir: Path) -> list[dict[str, str]]:
    """Read `<run_dir>/recordings.csv` back as a list of row dicts (Milestone O3's schema)."""
    return _read_csv_rows(run_dir / "recordings.csv")


def load_provenance(run_dir: Path) -> list[dict[str, str]]:
    """Read `<run_dir>/provenance.csv` back as a list of row dicts (Milestone O3's schema)."""
    return _read_csv_rows(run_dir / "provenance.csv")


# Milestone O7, Slice O7f: a fixed, purely presentational tie-break for
# rows sharing one `execution_seq` -- `execution_seq` is deterministic
# *observation* ordering only, never causality (architectural invariants
# #7/#8), and events from the same firing (a "used" event, its
# Recordings, and its "generated" event) commonly share one seq. Sorting
# by `execution_seq` alone would let two runs of the same replay present
# same-seq rows in a different, arbitrary order (whatever order the CSV
# happened to be read in) -- a *stable*, explicit tie-break keeps replay
# output deterministic without asserting any causal ordering the data
# does not actually guarantee. This is a fixed display convention, not a
# claim that "used" causally precedes "recording" precedes "generated".
_EVENT_TYPE_DISPLAY_PRIORITY = {"used": 0, "recording": 1, "generated": 2}


def render_replay_table(run_dir: Path) -> Table:
    """
    Build a Rich `Table` replaying one past Execution's Recordings and
    Provenance events together, grouped by `node_execution_id` --
    Milestone O7, Slice O7f: every row for one firing shares one
    `node_execution_id`, printed as its own column, so a reader never has
    to infer "these rows belong to the same firing" purely from equal
    `execution_seq` values. Rows are ordered by `execution_seq` first
    (the deterministic *observation* order, design record Section 13.1 --
    never causality, architectural invariants #7/#8), then by the fixed
    `_EVENT_TYPE_DISPLAY_PRIORITY` tie-break for rows sharing one seq, so
    output is stable across repeated calls without implying a stronger
    ordering guarantee than the data actually carries. Causality, where
    it exists, comes from the `provenance` rows' own `generated`/`used`
    relationships (Milestone O4), never from `execution_seq` position.
    """
    recordings = load_recordings(run_dir)
    provenance = load_provenance(run_dir)

    rows: list[tuple[int, int, str, str, str, str]] = []
    for row in recordings:
        rows.append(
            (
                int(row["execution_seq"]),
                _EVENT_TYPE_DISPLAY_PRIORITY["recording"],
                row["node_execution_id"],
                row["node_id"],
                "recording",
                f"{row['name']}={row['value']}",
            )
        )
    for row in provenance:
        rows.append(
            (
                int(row["execution_seq"]),
                _EVENT_TYPE_DISPLAY_PRIORITY[row["event_type"]]
                if row["event_type"] in _EVENT_TYPE_DISPLAY_PRIORITY
                else _EVENT_TYPE_DISPLAY_PRIORITY["generated"],
                row["node_execution_id"],
                row["node_id"],
                "provenance",
                f"{row['event_type']} {row['artifact_id']} v{row['artifact_version']}",
            )
        )
    rows.sort(key=lambda r: (r[0], r[1]))

    table = Table(title=f"Reed Execution Replay -- {run_dir.name}")
    table.add_column("seq", justify="right")
    table.add_column("node_execution_id")
    table.add_column("node")
    table.add_column("kind")
    table.add_column("detail")
    for seq, _priority, node_execution_id, node_id, kind, detail in rows:
        table.add_row(str(seq), node_execution_id[:8], node_id, kind, detail)

    return table


def print_replay(run_dir: Path, *, console: Console | None = None) -> None:
    """Render `run_dir`'s past Execution as a table to `console` (a fresh `Console()` if omitted)."""
    (console or Console()).print(render_replay_table(run_dir))
