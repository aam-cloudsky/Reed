"""
Terminal presentation policy (Milestone O7, Slice O7d).

The public API Reed users configure per Execution: **what is shown in the terminal**,
never **what Reed observes or persists**. This is a strict presentation-layer concern,
independent of Recordings/Provenance/Execution Trace collection (Milestone O2-O5) and of
whether durable storage or OTel export is configured (Milestone O3/O6) -- see the module
docstring of `reed.observability.presenter` for the consumer side of this split.

    Reed Runtime
         |
         +-- Execution Trace / Provenance / Recordings / Framework Errors
                      |
                      v
               Presentation Policy   <-- this module
                      |
                      v
               Terminal Renderer     <-- reed.observability.presenter

`observability="silent"` means "show nothing in the terminal." It never means "stop
collecting Recordings/Provenance," and it never disables durable storage or OTel export --
those are controlled independently via `storage_root=`/an OTel exporter adapter call, which
keep working unchanged regardless of terminal verbosity.

## Public API

```python
flow.run(observability="progress")     # a semantic preset -- the common case
flow.run(observability=PresentationPolicy(nodes=True, timings=True))  # escape hatch
flow.run()                              # default: PresentationPolicy.default() ("nodes")
```

A preset name is a string that compiles, once, into a `PresentationPolicy` -- a small,
immutable set of independent dimensions. Presets are documented combinations of those
dimensions, not a parallel mechanism: nothing a preset can express is inexpressible through
`PresentationPolicy(...)` directly, and nothing in `Run`/`NodeRuntime` ever branches on a
preset *name* -- only on the compiled `PresentationPolicy`'s dimensions. This is what keeps
adding a new preset, or a wholly different renderer, from requiring any change to
`Flow`/`Run` execution semantics (Milestone O7's own constraint, Section 2 of the task that
opened it: "the terminal is a consumer of observability information... it must never become
the observability model itself").

## Why semantic presets, not integer verbosity levels

An integer level (`observability=2`) is not self-documenting and its meaning drifts as more
levels are added later, forcing every user to memorize a table. A semantic preset name
(`"progress"`, `"verbose"`) states its own intent and is stable as the underlying
`PresentationPolicy` dimensions it compiles to evolve -- exactly the reasoning
`observability_goals.md`/`observability_non_goals.md` already apply to `Instrument.kind`
(a small, named, closed set) rather than an open-ended free-form value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PresentationPolicy:
    """
    A structured terminal presentation configuration -- the escape hatch
    beneath the preset strings, and what every preset compiles to.

    Each dimension is independent and boolean; there is no dimension whose
    meaning depends on another being set, so any combination is valid
    (`errors=False, nodes=True` is "show node lifecycle but suppress error
    lines" -- unusual, but not contradictory, and not rejected).

    - `errors`: print framework/Node errors (exceptions raised by a Node).
    - `progress`: render execution progress (see `reed.observability.presenter`
      for what "progress" can honestly mean in a reactive graph -- Section 6
      of the task that opened this milestone).
    - `nodes`: print one line per Node firing (start/finish, success/failure).
    - `propagation`: print full graph propagation (Artifact generation/
      consumption, indented by causal depth) -- the closest analogue to the
      pre-Issue-4 Bus/Depot/Outpost terminal experience, rebuilt on the new
      Execution Trace/Provenance foundation, never on the old Bus machinery.
    - `instruments`: print `ctx.record(...)` observations as they are accepted.
    - `timings`: include per-Node firing durations wherever `nodes`/
      `propagation` output already shows a line for that firing.
    """

    errors: bool = False
    progress: bool = False
    nodes: bool = False
    propagation: bool = False
    instruments: bool = False
    timings: bool = False

    @classmethod
    def silent(cls) -> "PresentationPolicy":
        """No terminal output at all -- e.g. Reed embedded inside another application."""
        return cls()

    @classmethod
    def default(cls) -> "PresentationPolicy":
        """
        `Flow.run()` with no `observability=` argument -- errors and node
        lifecycle, the smallest preset that still gives useful signal
        without dumping graph propagation. Matches the `"nodes"` preset.
        """
        return PRESETS["nodes"]


PRESETS: dict[str, PresentationPolicy] = {
    "silent": PresentationPolicy(),
    "errors": PresentationPolicy(errors=True),
    "progress": PresentationPolicy(errors=True, progress=True),
    "instruments": PresentationPolicy(errors=True, instruments=True),
    "nodes": PresentationPolicy(errors=True, nodes=True),
    "verbose": PresentationPolicy(
        errors=True,
        nodes=True,
        propagation=True,
        instruments=True,
        timings=True,
    ),
}


def resolve_presentation_policy(
    observability: "str | PresentationPolicy | None",
) -> PresentationPolicy:
    """
    Compile `Flow.run(observability=...)`'s argument into a
    `PresentationPolicy`. Accepts a preset name, an already-built
    `PresentationPolicy` (the escape hatch), or `None` (-> `.default()`).

    Raises `ValueError` for an unrecognized preset name, naming the valid
    presets, rather than silently falling back to a default -- an invalid
    configuration should fail clearly (Milestone O7's own test
    requirement), not be misinterpreted as some other mode.
    """
    if observability is None:
        return PresentationPolicy.default()
    if isinstance(observability, PresentationPolicy):
        return observability
    if isinstance(observability, str):
        try:
            return PRESETS[observability]
        except KeyError:
            raise ValueError(
                f"Unrecognized observability preset {observability!r} -- valid "
                f"presets are {sorted(PRESETS)!r}, or pass a PresentationPolicy(...) "
                "directly for a custom configuration."
            ) from None
    raise TypeError(
        f"observability= must be a preset name (str), a PresentationPolicy, or "
        f"None -- got {type(observability).__name__!r}."
    )
