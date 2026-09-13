"""
Instrument (Milestone O2, Slice O2a; redesigned at Milestone O7, Slice O7i --
typed Instrument Definitions, discovered dynamically at execution time).

## O7i redesign

The original (O1-O7h) design declared Instruments as *instances* of a plain
`Instrument` dataclass, constructed at module scope and threaded through
both `flow.add(node, instruments=[...])` (the FlowNode's declaration) and
`ctx.record(instrument, value)` (the Node body's usage) -- the same object
had to be imported in two unrelated places, which O7h's audit already
flagged as making a Node less self-contained (reused by a different Flow
with the same schema, the caller had to re-supply the same instance both
places).

Re-auditing this after O7h surfaced a stronger issue: prospective
declaration (`instruments=[...]`) is itself in tension with Reed's own
Artifact model, where a Node's *produced/consumed types* are the single
source of truth for what a Node does -- there is no second, parallel
"declare your outputs again" step for Artifacts. Instruments should follow
the same principle: **the Instrument type itself is the semantic
Instrument Definition** (docs/observability_goals.md Section 1's "the
logical unit of observation"), the same way an Artifact's Python type is
the semantic Artifact Definition (docs/architectural_decision.md). A
Node's declared Instrument schema is redundant with the type the Node
already references in its own body.

The corrected design:

    class Temperature(Instrument[float]):
        kind = InstrumentKind.GAUGE
        unit = "Cel"
        description = "Measured temperature"

    def track_temperature(ctx: NodeContext[None, Reading], reading: Reading) -> Reading:
        ctx.record(Temperature, reading.celsius)
        return reading

`Instrument[T]` is never instantiated -- the *class itself* is the value
passed to `ctx.record(...)` (`ctx.record(Temperature, ...)`, not
`ctx.record(Temperature(), ...)`). `Flow.add(...)` no longer accepts an
`instruments=` parameter at all: Instruments are **discovered dynamically
during execution** the first time a Node actually calls
`ctx.record(SomeInstrument, value)`, never prospectively declared by the
Flow. This is a deliberate non-goal boundary, not an oversight: static
`AST` inspection of a Node's body to recover "which Instrument classes
might this function call ctx.record(...) with" is explicitly rejected
(docs/observability_non_goals.md's general "no reflection-based magic"
posture) -- `describe`'s static, no-execution report
(`reed.observability.describe.describe_flow`) can therefore no longer
claim prospective Instrument knowledge; see that module's docstring for
how it now represents this honestly.

## Instrument Definition vs. Instrument Binding

The `Instrument` subclass itself (e.g. `Temperature`) is the **Instrument
Definition** -- a semantic, reusable type, exactly analogous to an
Artifact's domain type. The same `Instrument` subclass may be reused by
more than one Node in the same Flow (or across Flows) without conflict,
because a recorded `Recording`'s identity is never the bare Instrument
Definition alone -- it is always the **Instrument Binding**: the tuple
`(flow_id, node_id, Instrument)`, exactly mirroring how the same domain
Artifact type may only ever have one producer *within one Flow*
(architectural invariant #24) while still being an ordinary, freely
reusable Python type across Flows. `NodeRuntime._resolve_instrument(...)`
and `Recording.instrument_id` (`f"{flow_id}.{node_id}.{name}"`, unchanged
schema from O1-O7h) are what materialize this binding -- see
`node_runtime.py`.

## Typing

`Instrument[T]` is `Generic[T]`; `T` is the scalar Python type this
Instrument's Recordings carry (`float`, `int`, `str`, `bool`). Declaring
`class Temperature(Instrument[float])` and then calling
`ctx.record(Temperature, "not a float")` is a type error a static checker
(Pylance/Pyright) can catch through `NodeContext.record`'s own generic
signature (`record(self, instrument: type[Instrument[T]], value: T,
...)`  -- see `node_context.py`), as far as Python's type system
reasonably permits without a runtime dependent-type checker. Reed does not
additionally enforce this same T <-> value relationship at runtime beyond
the pre-existing scalar-type check (`docs/observability_non_goals.md`
Section 3) -- adding a full runtime type-check against a `Generic[T]`
parameter would require reading `__orig_bases__`/`__class_getitem__`
internals with no corresponding static-typing benefit, since a type
checker already catches the mismatch before the program runs.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Generic, TypeVar

T = TypeVar("T", bound="str | int | float | bool")


class InstrumentKind(Enum):
    """
    Restricted to `GAUGE`, `COUNTER`, and `UPDOWN_COUNTER` for V1
    (docs/observability_non_goals.md Section 2: no `Histogram`, no OTel
    Metric SDK types). `EVENT` is deliberately absent -- see Slice O2e
    (docs/observability_design.md Section 19) for its resolution: a
    lazily-named fact with no `Instrument` behind it at all is simply not
    an Instrument (Recording.kind is `None` for it).
    """

    GAUGE = "gauge"
    COUNTER = "counter"
    UPDOWN_COUNTER = "updown_counter"


class Instrument(Generic[T]):
    """
    A typed Instrument Definition (Milestone O7, Slice O7i). Never
    instantiated -- subclass it and pass the **class itself** to
    `ctx.record(...)`:

        class Temperature(Instrument[float]):
            kind = InstrumentKind.GAUGE
            unit = "Cel"
            description = "Measured temperature"

        ctx.record(Temperature, reading.celsius)

    `kind` and `unit` are required class attributes on every concrete
    subclass (validated at class-definition time by `__init_subclass__`,
    so a malformed Instrument definition fails at import time, not on
    first use deep inside a Run). `description` is optional and defaults
    to `""`, matching the original O2a `Instrument` dataclass's own
    default.

    See module docstring's "Instrument Definition vs. Instrument Binding"
    section for why the same subclass may be reused by multiple Nodes
    without conflating their Recordings.
    """

    kind: ClassVar[InstrumentKind]
    unit: ClassVar[str]
    description: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Deliberately skip validation for an intermediate subclass that
        # itself declares no `kind`/`unit` (e.g. a project's own shared
        # base class between `Instrument[T]` and its concrete leaves) --
        # only a class that actually sets `kind` in its own body is
        # validated here, so `cls.__dict__` (not `hasattr`, which would
        # also see inherited attributes) is checked directly. A concrete
        # leaf class that never sets `kind` anywhere in its MRO still
        # fails, via the `hasattr` check below, when Reed actually tries
        # to resolve it (`NodeRuntime._resolve_instrument`) -- this
        # `__init_subclass__` check exists to fail as early as possible
        # for the common case (a concrete class with a typo'd or missing
        # `kind`/`unit`), not to replace that later check entirely.
        if "kind" in cls.__dict__:
            kind = cls.__dict__["kind"]
            if not isinstance(kind, InstrumentKind):
                raise TypeError(
                    f"{cls.__name__}.kind must be an InstrumentKind member, "
                    f"got {kind!r} (docs/observability_non_goals.md Section 2 "
                    "-- no Histogram, no arbitrary kind values)."
                )
        if "unit" in cls.__dict__:
            unit = cls.__dict__["unit"]
            if not isinstance(unit, str):
                raise TypeError(
                    f"{cls.__name__}.unit must be a str, got {unit!r}."
                )

    @classmethod
    def instrument_name(cls) -> str:
        """
        The stable, globally-qualified name this Instrument Definition is
        identified by (`module.QualName`) -- used to build
        `Recording.name`/`Recording.instrument_id` (`node_runtime.py`).
        Deliberately derived from the class itself rather than requiring
        a redundant `name=` string, matching the "Instrument type *is*
        the Instrument Definition" principle above -- there is no second
        name to keep in sync with the class.
        """
        return f"{cls.__module__}.{cls.__qualname__}"
