"""
Post-hoc replay of a past Execution (Milestone O5, Slice O5c, optional).

Extends the O5b terminal renderer to also read `recordings.csv`/`provenance.csv` (Milestone
O3) for a Run whose process has already exited -- strictly more capable than the old
Bus-based system, which could only show live request/reply traffic (design record Section
8's "it can show provenance and recordings, not only Bus request/reply pairs").

This is read-only: it never reconstructs a live `Run`/`ExecutionTrace`, only a static
snapshot table built directly from the two CSV files a past Execution left behind under
`<storage_root>/runs/<execution_id>/`. It requires `storage_root` to have been configured for
that Execution (Milestone O3's opt-in) -- there is nothing to replay for an in-memory-only
Run, and this module raises `FileNotFoundError` rather than silently rendering an empty
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
            "execution_id, and did the Run actually fire any Nodes?"
        )
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_recordings(run_dir: Path) -> list[dict[str, str]]:
    """Read `<run_dir>/recordings.csv` back as a list of row dicts (Milestone O3's schema)."""
    return _read_csv_rows(run_dir / "recordings.csv")


def load_provenance(run_dir: Path) -> list[dict[str, str]]:
    """Read `<run_dir>/provenance.csv` back as a list of row dicts (Milestone O3's schema)."""
    return _read_csv_rows(run_dir / "provenance.csv")


def render_replay_table(run_dir: Path) -> Table:
    """
    Build a Rich `Table` replaying one past Execution's Recordings and
    Provenance events together, ordered by `execution_seq` -- the same
    deterministic-observation-order field every Level 1/2 record already
    carries (design record Section 13.1), so recordings and provenance
    events interleave in the order they were originally observed.
    """
    recordings = load_recordings(run_dir)
    provenance = load_provenance(run_dir)

    rows: list[tuple[int, str, str, str]] = []
    for row in recordings:
        rows.append(
            (
                int(row["execution_seq"]),
                row["node_id"],
                "recording",
                f"{row['name']}={row['value']}",
            )
        )
    for row in provenance:
        rows.append(
            (
                int(row["execution_seq"]),
                row["node_id"],
                "provenance",
                f"{row['event_type']} {row['artifact_id']} v{row['artifact_version']}",
            )
        )
    rows.sort(key=lambda r: r[0])

    table = Table(title=f"Reed Execution Replay -- {run_dir.name}")
    table.add_column("seq", justify="right")
    table.add_column("node")
    table.add_column("kind")
    table.add_column("detail")
    for seq, node_id, kind, detail in rows:
        table.add_row(str(seq), node_id, kind, detail)

    return table


def print_replay(run_dir: Path, *, console: Console | None = None) -> None:
    """Render `run_dir`'s past Execution as a table to `console` (a fresh `Console()` if omitted)."""
    (console or Console()).print(render_replay_table(run_dir))
