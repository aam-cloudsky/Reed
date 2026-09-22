"""
Terminal presentation policy (Milestone O7, Slice O7d; extended Milestone O8, Slice
O8b with `verbose_ops`).

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
keep working unchanged regardless of terminal verbosity. It also never disables structured
logging (Milestone O8): a `StructuredLogPresenter` is a separate, independently-configured
sink -- see `reed.observability.logging`.

## Public API

```python
flow.session(observability="progress")     # a semantic preset -- the common case
flow.session(observability=PresentationPolicy(nodes=True, timings=True))  # escape hatch
flow.session()                              # default: PresentationPolicy.default() ("nodes")
```

A preset name is a string that compiles, once, into a `PresentationPolicy` -- a small,
immutable set of independent dimensions. Presets are documented combinations of those
dimensions, not a parallel mechanism: nothing a preset can express is inexpressible through
`PresentationPolicy(...)` directly, and nothing in `Session`/`NodeSession` ever branches on a
preset *name* -- only on the compiled `PresentationPolicy`'s dimensions. This is what keeps
adding a new preset, or a wholly different renderer, from requiring any change to
`Flow`/`Session` execution semantics (Milestone O7's own constraint, Section 2 of the task that
opened it: "the terminal is a consumer of observability information... it must never become
the observability model itself").

## Why semantic presets, not integer verbosity levels

An integer level (`observability=2`) is not self-documenting and its meaning drifts as more
levels are added later, forcing every user to memorize a table. A semantic preset name
(`"progress"`, `"verbose"`) states its own intent and is stable as the underlying
`PresentationPolicy` dimensions it compiles to evolve -- exactly the reasoning
`observability_goals.md`/`observability_non_goals.md` already apply to `Instrument.kind`
(a small, named, closed set) rather than an open-ended free-form value.

## Detail level vs. logging severity (Milestone O8)

`verbose_ops` is a *presentation detail level*, not a logging severity (docs/
logging_design.md Section 7): it controls whether artifact-publication/instrument lines
render in the compact "what was published" grammar or the explicit "which operation
(CONSUME/RECORD/COMMIT) happened" grammar (`reed.observability.presenter`). It never
affects `LogEvent.severity`, which is a property of the underlying fact
(`node_error` is always `"error"`), nor what Reed computes, collects, or persists
(docs/observability_invariants.md #34).
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
    - `propagation`: print graph propagation -- Artifact generation/
      consumption between Nodes and the Repository (Milestone O8, Slice
      O8b) -- the closest analogue to the pre-Issue-4 Bus/Depot/Outpost
      terminal experience, rebuilt on the Execution Trace/Provenance
      foundation, never on the old Bus machinery.
    - `instruments`: print `ctx.record(...)` observations as they are accepted.
    - `timings`: include per-Node firing durations wherever `nodes`/
      `propagation` output already shows a line for that firing.
    - `verbose_ops` (Milestone O8): when `propagation`/`instruments` are also
      set, render the explicit per-operation grammar (`CONSUME`/`RECORD`/
      `COMMIT`) instead of the compact "Artifact@vN -> REPOSITORY" grammar.
      Purely a detail-level choice -- see the module docstring's "Detail
      level vs. logging severity" section.
    """

    errors: bool = False
    progress: bool = False
    nodes: bool = False
    propagation: bool = False
    instruments: bool = False
    timings: bool = False
    verbose_ops: bool = False

    @classmethod
    def silent(cls) -> "PresentationPolicy":
        """No terminal output at all -- e.g. Reed embedded inside another application."""
        return cls()

    @classmethod
    def default(cls) -> "PresentationPolicy":
        """
        `Flow.session()` with no `observability=` argument -- errors and node
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
    "propagation": PresentationPolicy(errors=True, propagation=True),
    "verbose": PresentationPolicy(
        errors=True,
        nodes=True,
        propagation=True,
        instruments=True,
        timings=True,
        verbose_ops=True,
    ),
}


def resolve_presentation_policy(
    observability: "str | PresentationPolicy | None",
) -> PresentationPolicy:
    """
    Compile `Flow.session(observability=...)`'s argument into a
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
