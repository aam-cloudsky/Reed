"""
Reed multiple-instance execution example (issue "Support multiple
artifact instances and per-instance node execution", slices MI-A
through MI-J).

Demonstrates the mechanism end to end, using the same running example
the design plan itself uses: a small fleet of aircraft, each identified
by its own `InstanceKey` (its tail number), tracked by the same `Flow`
at once.

    - InstanceKey / feed_instances(): commit several instances of the
      same domain type in one call (Slice MI-A/MI-D).
    - Per-instance firing: each aircraft's own `perception` firing sees
      only ITS OWN last-known values, never another aircraft's
      (Slice MI-E).
    - Per-instance NodeMemory / last_output: each aircraft's climb-rate
      tracking is independent (Slice MI-F).
    - Broadcasting: a shared `DeltaT` (time step), fed once via plain
      `feed()`, participates in every aircraft's own firing -- and its
      freshness correctly expires after one push(), so a node declared
      with the default `TriggerPolicy.ALL_INPUTS_CHANGED` does not
      spuriously refire just because one aircraft's own state changed
      (Slice MI-G).
    - Collective dependency: `fleet_summary` reads the currently known
      set of every aircraft's latest `Observation` at once, via
      `Annotated[Observation, Collective]` (Slice MI-H) -- fed by its
      own, separate `FleetTick`, kept deliberately apart from `DeltaT`
      so the Collective read is never torn mid-cascade (Slice MI-I's
      own documented Quiescence resolution: "feed the complete batch,
      then push()").
    - Lifecycle: an aircraft leaving the fleet is removed per (domain
      type, instance) pair via `Session.remove_instance(...)`
      (Slice MI-I).
    - `Snapshot.instances(domain_type)`: the multi-instance-aware
      complement to `Snapshot.get(...)`/`snapshot[...]`, showing every
      aircraft's latest `Observation` at once.
    - Observability: `instance_id` on provenance events and the
      provenance graph correctly distinguishes which aircraft produced
      or consumed which artifact version (Slice MI-J).

Run it directly:

    uv run python examples/multi_instance_fleet_example.py
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from rich.console import Console

from reed import Flow, NodeContext
from reed.composition.node.collective import Collective
from reed.execution.instance_key import InstanceKey
from reed.observability.graph import render_provenance_tree
from reed.observability.replay import load_provenance


# ============================================================================
# Domain types
# ============================================================================


@dataclass
class AircraftState:
    """Externally fed, once per aircraft, per tick -- session.feed_instances(...)."""

    altitude: float


@dataclass
class DeltaT:
    """The shared time step -- fed ONCE via plain feed(), never per aircraft."""

    seconds: float


@dataclass
class Observation:
    """perception's own per-aircraft output: latest altitude and climb rate."""

    altitude: float
    climb_rate: float


@dataclass
class FleetTick:
    """
    A separate trigger, deliberately apart from DeltaT, solely to ask
    fleet_summary to read the fleet's current state -- fed only after a
    push() that already let every aircraft's own perception firing
    settle, so the Collective read below is never torn mid-cascade.
    """


@dataclass
class FleetSummary:
    average_altitude: float
    count: int


@dataclass
class ClimbRateMemory:
    previous_altitude: float | None = None


# ============================================================================
# Tail numbers -- one InstanceKey per aircraft in the fleet
# ============================================================================

TAIL_ALPHA = InstanceKey(key="N-ALPHA")
TAIL_BRAVO = InstanceKey(key="N-BRAVO")
TAIL_CHARLIE = InstanceKey(key="N-CHARLIE")


# ============================================================================
# Nodes
# ============================================================================


def perception(
    ctx: NodeContext[ClimbRateMemory, Observation],
    state: AircraftState,
    dt: DeltaT,
) -> Observation:
    """
    Fires once per aircraft (Slice MI-E): `state` is always THIS
    aircraft's own last-known AircraftState, never another's. `dt` is
    the shared, broadcast DeltaT (Slice MI-G) -- visible to every
    aircraft's firing even though it was fed only once, at singleton
    scope. `ctx.memory` is this aircraft's own independent NodeMemory
    (Slice MI-F): a different aircraft's `perception` firing never sees
    or mutates it.
    """
    previous = ctx.memory.previous_altitude
    climb_rate = (state.altitude - previous) / dt.seconds if previous is not None else 0.0
    ctx.memory.previous_altitude = state.altitude
    return Observation(altitude=state.altitude, climb_rate=climb_rate)


def fleet_summary(
    tick: FleetTick,
    observations: Annotated[Observation, Collective],
) -> FleetSummary:
    """
    Fires once, at singleton scope, whenever FleetTick is fed.
    `observations` (Slice MI-H) is the currently known collection of
    EVERY aircraft's latest Observation, resolved fresh at firing time --
    never one scalar aircraft's value. A Collective-marked parameter is
    always SAMPLED (see collective.py): its own arrival never triggers
    this node by itself, only FleetTick does.
    """
    if not observations:
        return FleetSummary(average_altitude=0.0, count=0)
    return FleetSummary(
        average_altitude=sum(o.altitude for o in observations) / len(observations),
        count=len(observations),
    )


def main() -> None:
    console = Console()
    flow = Flow()
    flow.add(perception)
    flow.add(fleet_summary)
    session = flow.session()

    print("=" * 78)
    print("Tick 1: three aircraft report altitude together, one shared DeltaT")
    print("=" * 78)

    session.feed(DeltaT(seconds=1.0))
    session.feed_instances(
        {
            TAIL_ALPHA: AircraftState(altitude=1000.0),
            TAIL_BRAVO: AircraftState(altitude=2000.0),
            TAIL_CHARLIE: AircraftState(altitude=3000.0),
        }
    )
    session.push()

    for tail in (TAIL_ALPHA, TAIL_BRAVO, TAIL_CHARLIE):
        obs = session.repository.get_artifact_record(Observation, instance=tail).value
        print(f"  {tail.key}: altitude={obs.altitude:>7.1f}  climb_rate={obs.climb_rate:+.1f}")

    # fleet_summary is asked to read the fleet's state via its OWN,
    # separate FleetTick -- fed only now, after perception's own cascade
    # for this push() has already fully settled for every aircraft.
    session.feed(FleetTick())
    session.push()
    summary = session.repository.get_artifact_record(FleetSummary).value
    print(f"  fleet_summary: average_altitude={summary.average_altitude:.1f}  count={summary.count}")

    print()
    print("=" * 78)
    print("Tick 2: only N-ALPHA reports a new altitude -- DeltaT is NOT re-fed")
    print("=" * 78)

    session.feed_instances({TAIL_ALPHA: AircraftState(altitude=1100.0)})
    session.push()

    obs_alpha = session.repository.get_artifact_record(Observation, instance=TAIL_ALPHA).value
    print(f"  N-ALPHA's own Observation: altitude={obs_alpha.altitude:.1f} (unchanged -- correct)")
    print(
        "  perception correctly did NOT refire for N-ALPHA: DeltaT's own freshness"
        " is spent after one push(), not permanent, so ALL_INPUTS_CHANGED"
        " (perception's default trigger_policy) genuinely waits for a fresh"
        " DeltaT, not just any per-aircraft arrival."
    )

    print()
    print("=" * 78)
    print("Tick 3: N-ALPHA reports again, AND DeltaT is re-fed -- perception refires")
    print("=" * 78)

    session.feed(DeltaT(seconds=2.0))
    session.feed_instances({TAIL_ALPHA: AircraftState(altitude=1300.0)})
    session.push()

    obs_alpha = session.repository.get_artifact_record(Observation, instance=TAIL_ALPHA).value
    print(f"  N-ALPHA: altitude={obs_alpha.altitude:.1f}  climb_rate={obs_alpha.climb_rate:+.1f}")
    print(
        "  climb_rate = (1300.0 - 1000.0) / 2.0 seconds = "
        f"{(1300.0 - 1000.0) / 2.0:+.1f} -- NOT (1300 - 1100), because Tick 2's"
        " feed of 1100.0 never caused perception to actually FIRE for"
        " N-ALPHA (no fresh DeltaT that tick), so N-ALPHA's own"
        " NodeMemory never advanced past Tick 1's altitude (1000.0)."
        " NodeMemory reflects the last FIRING, not the last feed() --"
        " N-BRAVO's and N-CHARLIE's own memory were never touched by"
        " this firing either way."
    )

    print()
    print("=" * 78)
    print("Snapshot.instances(): every aircraft's latest Observation at once")
    print("=" * 78)

    snapshot = session.snapshot()
    for tail, obs in snapshot.instances(Observation).items():
        print(f"  {tail.key}: altitude={obs.altitude:.1f}  climb_rate={obs.climb_rate:+.1f}")

    print()
    print("=" * 78)
    print("Lifecycle: N-CHARLIE leaves the fleet")
    print("=" * 78)

    # Scoped per (domain type, instance) pair (Slice MI-I) -- N-CHARLIE
    # appears under both AircraftState and Observation, so both are
    # removed explicitly; there is no single cross-type "remove this
    # aircraft entirely" call, by design.
    session.remove_instance(AircraftState, TAIL_CHARLIE)
    session.remove_instance(Observation, TAIL_CHARLIE)

    session.feed(FleetTick())
    session.push()
    summary = session.repository.get_artifact_record(FleetSummary).value
    print(
        f"  fleet_summary after removal: average_altitude={summary.average_altitude:.1f}"
        f"  count={summary.count} (N-CHARLIE no longer counted)"
    )

    # ------------------------------------------------------------------
    # Observability (Slice MI-J): instance_id distinguishes which
    # aircraft produced or consumed which artifact version.
    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print("Observability: instance_id in provenance and the provenance graph")
    print("=" * 78)

    with tempfile.TemporaryDirectory() as tmp:
        storage_root = Path(tmp) / ".reed"
        obs_flow = Flow()
        obs_flow.add(perception)
        obs_session = obs_flow.session(storage_root=str(storage_root))

        obs_session.feed(DeltaT(seconds=1.0))
        obs_session.feed_instances(
            {TAIL_ALPHA: AircraftState(altitude=1000.0), TAIL_BRAVO: AircraftState(altitude=2000.0)}
        )
        obs_session.push()

        run_dir = storage_root / "runs" / obs_session.execution_id
        rows = load_provenance(run_dir)

        print("  provenance rows for Observation (\"generated\"):")
        for row in rows:
            if row["event_type"] == "generated" and row["artifact_id"].endswith("Observation"):
                print(f"    v{row['artifact_version']}  instance_id={row['instance_id']}")

        print()
        print("  provenance graph (each aircraft's own Observation is a distinct node):")
        console.print(render_provenance_tree(run_dir))


if __name__ == "__main__":
    main()
