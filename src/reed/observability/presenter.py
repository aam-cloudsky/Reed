"""
Terminal presenter (Milestone O7, Slice O7d/O7e; extended Milestone O8, Slice O8b for
artifact-publication rendering and structured-logging fan-out).

The consumer side of `reed.observability.presentation.PresentationPolicy`: turns a
compiled policy into a live renderer, invoked by `Session` at the same hook points that
already exist for Provenance/Execution Trace emission (`_fire`, `publish`) -- never a
new observability collection mechanism of its own. A `Presenter` reads identity/timing
data `Session` already has and prints; it never decides what Reed observes, persists, or
exports.

    Reed Runtime
         |
         +-- identity / Execution Trace / Provenance / Recordings  (unchanged, Milestones O1-O6)
                      |
                      v
               PresentationPolicy          (reed.observability.presentation)
                      |
                      v
               Presenter (this module)     <-- Rich is an implementation detail here only

Rich is used internally for rendering, but nothing in `Session`/`NodeContext`/`Flow`'s public
surface exposes Rich, tqdm, or any other backend-specific vocabulary -- `PresentationPolicy`
and the `"silent"`/`"errors"`/`"progress"`/`"instruments"`/`"nodes"`/`"verbose"` preset names
are Reed's own words for what the user is choosing to see.

## Progress semantics (Slice O7e)

A percentage/fraction progress bar ("5/8 Nodes") requires a stable, known denominator. In a
reactive graph, the set of Nodes that will actually fire for one `publish(...)` call is not
knowable in advance: `TriggerPolicy.MANUAL` Nodes never auto-fire, `ALL_INPUTS_CHANGED`
Nodes wait for every input to go fresh (may not happen this cascade at all), branching and
joins mean the discovered frontier grows and shrinks as the cascade runs, and a Node can
raise before producing a value that would otherwise have triggered more firings. Reporting
`"5/8"` would assert a denominator Reed cannot honestly justify.

Instead, `"progress"` renders an **indeterminate** live counter -- a spinner plus "Processed
N nodes" -- accurate under any TriggerPolicy mix, any branching/join shape, and (Section 14
of the task that opened this milestone) unaffected by a future parallel execution model:
concurrent firings still each report their own start/finish independently, and a completed-
count still only ever increases, never requiring Reed to have predicted how many firings
there would be.

## Artifact-publication rendering (Milestone O8, Slice O8b)

`on_artifact_generated`/`on_artifact_consumed` are new hooks (docs/logging_design.md
Section 3): `Session._fire` already knows, at the exact moment it emits a `"generated"`/
`"used"` `ProvenanceEvent`, everything needed to render "Node X published Artifact@vN to
the Repository" -- this only exposes that same moment to the `Presenter`, it does not add
any new observation. Rendered only when `PresentationPolicy.propagation` is set (the
"show data flow" dimension), using the compact/verbose visual grammar
`docs/logging_design.md` Section 6 defines; see `_render_artifact_generated` below.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from rich.console import Console
from rich.text import Text

from reed.observability.presentation import PresentationPolicy

if TYPE_CHECKING:
    from reed.observability.identity import NodeExecutionIdentity
    from reed.observability.recording import Recording


class Presenter:
    """
    Base presenter: every hook is a no-op. `Session` always holds a
    `Presenter` (never `None`), so every call site can call a hook
    unconditionally -- `NullPresenter` (the `"silent"` preset) is simply
    this base class used directly, with nothing to override.
    """

    def on_publish_start(self, domain_value: object) -> None: ...

    def on_publish_end(self) -> None: ...

    def on_node_started(self, identity: "NodeExecutionIdentity", *, depth: int) -> None: ...

    def on_node_finished(
        self, identity: "NodeExecutionIdentity", *, depth: int, duration: float
    ) -> None: ...

    def on_node_error(
        self, identity: "NodeExecutionIdentity", exc: BaseException, *, duration: float
    ) -> None: ...

    def on_recording(self, recording: "Recording") -> None: ...

    def on_artifact_generated(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None: ...

    def on_artifact_consumed(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None: ...


NullPresenter = Presenter


def _short_id(node_execution_id: str) -> str:
    """
    A 6-hex-char rendering of `node_execution_id` -- enough to visually
    correlate lines from the same firing without the noise of a full UUID
    (docs/logging_design.md Section 6). Never itself a causality claim
    (`docs/observability_invariants.md` #9): two lines sharing a short id
    mean "same firing," nothing about ordering between other lines.
    """
    return node_execution_id[:6]


class TerminalPresenter(Presenter):
    """
    A `Presenter` driven by a `PresentationPolicy`, rendering to a Rich
    `Console`. Each dimension renders independently -- a caller can combine
    any subset via `PresentationPolicy(...)` directly, not only a preset.
    """

    def __init__(
        self, policy: PresentationPolicy, *, console: "Console | None" = None
    ) -> None:
        self._policy = policy
        self._console = console or Console()
        self._nodes_processed = 0
        self._progress = None
        self._progress_task = None

    def on_publish_start(self, domain_value: object) -> None:
        if self._policy.progress:
            from rich.progress import Progress, SpinnerColumn, TextColumn

            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self._console,
                transient=False,
            )
            self._progress.start()
            self._progress_task = self._progress.add_task(
                f"Processing {type(domain_value).__name__}...", total=None
            )

    def on_publish_end(self) -> None:
        if self._progress is not None:
            self._progress.stop()
            self._progress = None
            self._progress_task = None

    def on_node_started(self, identity: "NodeExecutionIdentity", *, depth: int) -> None:
        if self._policy.propagation and self._policy.verbose_ops:
            indent = "    " * depth
            self._console.print(f"{indent}[dim]-> {identity.node_id}[/dim]")

    def on_node_finished(
        self, identity: "NodeExecutionIdentity", *, depth: int, duration: float
    ) -> None:
        self._nodes_processed += 1

        if self._progress is not None and self._progress_task is not None:
            self._progress.update(
                self._progress_task,
                description=f"Processed {self._nodes_processed} nodes",
            )

        if self._policy.nodes or (self._policy.propagation and self._policy.verbose_ops):
            indent = "    " * depth if self._policy.propagation else ""
            timing = f" [dim]({duration * 1000:.1f}ms)[/dim]" if self._policy.timings else ""
            self._console.print(f"{indent}[green]✓[/green] {identity.node_id}{timing}")

    def on_node_error(
        self, identity: "NodeExecutionIdentity", exc: BaseException, *, duration: float
    ) -> None:
        if self._policy.errors:
            marker = Text("● ", style="bold red")
            marker.append("ERROR", style="bold red")
            marker.append(f" ({_short_id(identity.node_execution_id)})   ", style="dim")
            marker.append(identity.node_id, style="yellow")
            marker.append(f": {exc}")
            self._console.print(marker)

    def on_recording(self, recording: "Recording") -> None:
        if not self._policy.instruments:
            return
        unit = f" {recording.unit}" if recording.unit else ""
        if self._policy.verbose_ops:
            line = Text("● ", style="cyan")
            line.append("RECORD".ljust(9), style="cyan")
            line.append(f"({_short_id(recording.node_execution_id)})   ", style="dim")
            line.append(recording.node_id.ljust(20), style="yellow")
            line.append(" → ")
            line.append(f"{recording.name} {recording.value}{unit}")
            self._console.print(line)
        else:
            self._console.print(f"  {recording.name:<20} {recording.value}{unit}")

    def on_artifact_generated(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        if not self._policy.propagation:
            return
        short_id = _short_id(identity.node_execution_id)
        if self._policy.verbose_ops:
            line = Text("● ", style="green")
            line.append("COMMIT".ljust(9), style="cyan")
            line.append(f"({short_id})   ", style="dim")
            line.append(identity.node_id.ljust(20), style="yellow")
            line.append(" → ")
            line.append(f"{artifact_type}@v{artifact_version}", style="bold")
            self._console.print(line)
        else:
            line = Text("● ", style="green")
            line.append(f"{artifact_type}@v{artifact_version}".ljust(22), style="bold")
            line.append(f"({short_id})   ", style="dim")
            line.append(identity.node_id, style="yellow")
            line.append(" → ")
            line.append("REPOSITORY", style="magenta")
            self._console.print(line)

    def on_artifact_consumed(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        if not (self._policy.propagation and self._policy.verbose_ops):
            # Normal mode shows net publication only (Section 6: consumption
            # is implied by the next line's producer, never spelled out
            # twice) -- verbose mode is the only place CONSUME is explicit.
            return
        short_id = _short_id(identity.node_execution_id)
        line = Text("● ", style="green")
        line.append("CONSUME".ljust(9), style="cyan")
        line.append(f"({short_id})   ", style="dim")
        line.append(f"{artifact_type}@v{artifact_version}".ljust(20))
        line.append(" → ")
        line.append(identity.node_id, style="yellow")
        self._console.print(line)


class CompositePresenter(Presenter):
    """
    Fans one `Session`'s `Presenter` calls out to several concrete `Presenter`s
    (Milestone O8, Slice O8b) -- e.g. a `TerminalPresenter` for humans and a
    `StructuredLogPresenter` (`reed.observability.logging`) for a JSON sink,
    built from the same underlying facts. `Session` still only ever holds and
    calls one `Presenter`; this class is the only place that knows there is
    more than one.

    Each sub-presenter's hook call is isolated individually so that one
    broken sub-presenter cannot prevent another from receiving the same
    call (docs/observability_invariants.md #31) -- on top of, not instead
    of, `Session._safe_presenter_call`'s own isolation of the composite call
    itself.
    """

    def __init__(self, presenters: "list[Presenter]") -> None:
        self._presenters = list(presenters)

    def _fan_out(self, method_name: str, *args: object, **kwargs: object) -> None:
        for presenter in self._presenters:
            try:
                getattr(presenter, method_name)(*args, **kwargs)
            except BaseException:  # noqa: BLE001 -- isolate each sub-presenter independently
                pass

    def on_publish_start(self, domain_value: object) -> None:
        self._fan_out("on_publish_start", domain_value)

    def on_publish_end(self) -> None:
        self._fan_out("on_publish_end")

    def on_node_started(self, identity: "NodeExecutionIdentity", *, depth: int) -> None:
        self._fan_out("on_node_started", identity, depth=depth)

    def on_node_finished(
        self, identity: "NodeExecutionIdentity", *, depth: int, duration: float
    ) -> None:
        self._fan_out("on_node_finished", identity, depth=depth, duration=duration)

    def on_node_error(
        self, identity: "NodeExecutionIdentity", exc: BaseException, *, duration: float
    ) -> None:
        self._fan_out("on_node_error", identity, exc, duration=duration)

    def on_recording(self, recording: "Recording") -> None:
        self._fan_out("on_recording", recording)

    def on_artifact_generated(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        self._fan_out(
            "on_artifact_generated", identity, artifact_type=artifact_type, artifact_version=artifact_version
        )

    def on_artifact_consumed(
        self, identity: "NodeExecutionIdentity", *, artifact_type: str, artifact_version: int
    ) -> None:
        self._fan_out(
            "on_artifact_consumed", identity, artifact_type=artifact_type, artifact_version=artifact_version
        )


def build_presenter(
    policy: PresentationPolicy, *, console: "Console | None" = None
) -> Presenter:
    """
    Compile `policy` into a `Presenter`. `PresentationPolicy()` (the
    `"silent"` preset -- every dimension `False`) returns a plain
    `NullPresenter` rather than a `TerminalPresenter` with nothing to
    render: no Rich `Console` is even constructed, so `observability=
    "silent"` costs nothing beyond the policy comparison itself.
    """
    if policy == PresentationPolicy():
        return NullPresenter()
    return TerminalPresenter(policy, console=console)
