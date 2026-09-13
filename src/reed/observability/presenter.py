"""
Terminal presenter (Milestone O7, Slice O7d/O7e).

The consumer side of `reed.observability.presentation.PresentationPolicy`: turns a
compiled policy into a live renderer, invoked by `Run` at the same hook points that
already exist for Provenance/Execution Trace emission (`_fire`, `publish`) -- never a
new observability collection mechanism of its own. A `Presenter` reads identity/timing
data `Run` already has and prints; it never decides what Reed observes, persists, or
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

Rich is used internally for rendering, but nothing in `Run`/`NodeContext`/`Flow`'s public
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
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from reed.observability.presentation import PresentationPolicy

if TYPE_CHECKING:
    from reed.observability.identity import NodeExecutionIdentity
    from reed.observability.recording import Recording


class Presenter:
    """
    Base presenter: every hook is a no-op. `Run` always holds a
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


NullPresenter = Presenter


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
        if self._policy.propagation:
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

        if self._policy.nodes or self._policy.propagation:
            indent = "    " * depth if self._policy.propagation else ""
            timing = f" [dim]({duration * 1000:.1f}ms)[/dim]" if self._policy.timings else ""
            self._console.print(f"{indent}[green]✓[/green] {identity.node_id}{timing}")

    def on_node_error(
        self, identity: "NodeExecutionIdentity", exc: BaseException, *, duration: float
    ) -> None:
        if self._policy.errors:
            self._console.print(
                f"[bold red]ERROR[/bold red] {identity.node_id}: {exc}"
            )

    def on_recording(self, recording: "Recording") -> None:
        if self._policy.instruments:
            unit = f" {recording.unit}" if recording.unit else ""
            self._console.print(f"  {recording.name:<20} {recording.value}{unit}")


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
