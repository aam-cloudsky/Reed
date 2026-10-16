"""
Typed domain signature parsing (Slice 1A).

Scope for this slice (docs/refactor_priority_order.md, Milestone 1, Slice
1A -- Priority 1 + part of Priority 4; docs/parcel_boundary_decision.md;
docs/node_context_decision.md):

    1. parse domain artifact parameters (plain domain types, not Parcel
       subclasses);
    2. detect an injected `NodeContext[MemoryType, OutputType]` parameter;
    3. exclude the detected `NodeContext` parameter from dataflow input
       parameters (architectural_invariants.md #12);
    4. validate `NodeContext[MemoryType, OutputType]`'s output type
       against the function's return type (architectural_invariants.md,
       node_context_decision.md, Strong Typing Rule);
    5. reject self-flow signatures: a node must not consume and produce
       the same domain artifact type (architectural_invariants.md #11,
       parcel_boundary_decision.md, "No Self-Flow").

Explicitly out of scope for this slice (see docs/refactor_priority_order.md,
Milestones And Slices, Slice 1B and later):

    - `ArtifactDescriptor` (Priority 3) does not exist yet. This parser
      produces its own minimal `DomainNodeSignature` result instead of
      artifact descriptors.
    - `NodeDescription` / `NodeDefinition` (Priority 2) are not modified
      to use this parser. The existing Parcel-centric
      `NodeDescriptionBuilder` (`reed.composition.node.node_builder`)
      remains the current, regression-protected path -- this module is
      additive, not a replacement (docs/refactor_state.md, Known
      Compatibility Layer).
    - Duplicate-producer validation across a `Flow` (Priority 8,
      `DependencyRegistry`) is a Flow-composition-level concern and is
      not implemented here; this parser only validates one function's own
      signature in isolation.

Slice 1F addition, refined by a Slice 1F follow-up (maintenance, not
a new architectural slice): `__init__` accepts an optional
`extra_globalns`, merged into `function.__globals__` before resolving
type hints. A node function's string annotations (`from __future__
import annotations`) can only reference names present in
`function.__globals__` (its defining module) -- a name imported
inside a function/test body (for example `NodeContext` imported
locally right before calling `Flow.add(...)`) is not part of that.
Defaults to `None`, which preserves this parser's original Slice 1A
behavior exactly: normal resolution via `function.__globals__` alone.

Known limitation (for future maintainers of composition/signature
resolution):

    Reed first resolves annotations using the function's normal
    defining namespace. As a compatibility fallback for locally
    defined nodes registered immediately with `Flow.add(...)`, the
    caller's local namespace may be used once. This does not
    guarantee resolution for functions returned through arbitrary
    wrapper/factory scopes.

The retry itself lives in `Flow.add(...)`
(`flow_composition.py`), not here: it attempts resolution normally
first (no `extra_globalns`) and only retries once, with its own
immediate caller's locals merged in as `extra_globalns`, if that
first attempt raises `NameError`. This parser's own behavior --
merge `extra_globalns` into `globalns` when given, do nothing extra
when not -- is unchanged from the original Slice 1F addition.

Slice 21B (GitHub issue #21) addition: `get_type_hints` is now called
with `include_extras=True`, so an `Annotated[T, Sampled]`-annotated
consumed parameter (`reed.composition.node.sampled.Sampled`) survives
resolution instead of silently collapsing to plain `T`
(references/ingested/sampled-input-annotated-detection-gap.md records
this as a real, implementation-blocking gap in the original proposal).
Every annotation this parser reads is unwrapped back down to its
underlying type (`_unwrap_annotated`) before any identity/equality
comparison (self-flow rejection, `NodeContext` detection, the produced
return type) -- `Annotated[...]`'s only externally visible effect in
this module is which parameter names land in the new
`sampled_parameter_names` result field. `NodeContext[MemoryType,
OutputType]` detection (`get_origin(annotation) is NodeContext`) is a
plain generic subscript, never wrapped in `Annotated`, and is therefore
unaffected by this change -- confirmed by
tests/test_slice_21b_sampled_annotation_detection.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature, iscoroutinefunction, signature
from typing import (
    Annotated,
    Callable,
    TypeAlias,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from reed.composition.node.collective import Collective, CollectiveMarker
from reed.composition.node.node_context import NodeContext
from reed.composition.node.sampled import Sampled

DomainConsumedParameter: TypeAlias = tuple[str, type]


@dataclass(frozen=True)
class DomainNodeSignature:
    """
    Result of parsing one typed domain function signature.

    This is intentionally not `NodeDescription` (Priority 2) and does not
    use `ArtifactDescriptor` (Priority 3) -- both belong to Slice 1B.

    `sampled_parameter_names` (Slice 21B) is additive: the subset of
    `consumed_parameters`' names (by name, not by type -- a name is
    unambiguous, matching how `consumed_parameters` itself is already
    keyed) whose annotation was `Annotated[T, Sampled]`. Deliberately a
    separate field rather than a third element on
    `DomainConsumedParameter` (`tuple[str, type]`): this module produces
    no `ArtifactDescriptor`/`InputRole` (see class docstring above --
    that is Slice 1B's/21A's concern), so it exposes only the raw fact
    an annotation carried the `Sampled` marker, leaving the
    `InputRole` naming decision to `DomainNodeDescriptionBuilder`
    (`domain_node_description.py`), which already owns
    `ArtifactDescriptor` construction.
    """

    function: Callable
    consumed_parameters: tuple[DomainConsumedParameter, ...]
    context_parameter_name: str | None
    context_memory_type: type | None
    context_output_type: type | None
    produced_type: type
    sampled_parameter_names: frozenset[str] = frozenset()
    # Slice MI-H (docs/refactor/multi_instance_execution_plan.md Section
    # 5 item 8 -- Collective dependencies): the subset of
    # `consumed_parameters`' names whose annotation was
    # `Collective[T]` (`reed.composition.node.collective.Collective`,
    # i.e. `Annotated[tuple[T, ...], CollectiveMarker]`). Detected exactly like `sampled_parameter_names`
    # (Slice 21B), independently -- a parameter may in principle carry
    # both markers' metadata at once, though no current use case combines
    # them.
    collective_parameter_names: frozenset[str] = frozenset()


class DomainNodeSignatureParser:
    """
    Parses a typed Python callable into a `DomainNodeSignature`.

    See module docstring for the exact Slice 1A scope. This parser does
    not touch `NodeDescriptionBuilder`, `NodeDescription`, or
    `NodeDefinition`.
    """

    def __init__(
        self,
        function: Callable,
        *,
        extra_globalns: dict[str, object] | None = None,
    ) -> None:
        self._function = function
        self._signature: Signature = signature(function)

        globalns = dict(function.__globals__)
        if extra_globalns:
            globalns.update(extra_globalns)

        # Slice 21B: include_extras=True is required for Annotated[T, Sampled]
        # to survive resolution at all -- see this module's docstring and
        # references/ingested/sampled-input-annotated-detection-gap.md.
        self._type_hints = get_type_hints(
            function, globalns=globalns, include_extras=True
        )

    def parse(self) -> DomainNodeSignature:
        if iscoroutinefunction(self._function):
            raise TypeError(
                f"Node function '{self._function.__name__}' cannot be async."
            )

        if "return" not in self._type_hints:
            raise TypeError(
                f"Node function '{self._function.__name__}' "
                "must declare a return type."
            )

        # Slice 21B: unwrap defensively -- Sampled has no meaning on a
        # return type (it is not a designed use case), but produced_type
        # must always be a plain type (ArtifactDescriptor.domain_type's
        # own contract), never an Annotated[...] object, regardless of
        # what include_extras=True now surfaces here. Any metadata on a
        # return annotation is silently discarded, matching this
        # parser's pre-21B behavior for every currently passing test
        # (none annotates a return type with Annotated).
        produced_type, _, _ = self._unwrap_annotated(self._type_hints["return"])

        (
            consumed_parameters,
            sampled_parameter_names,
            collective_parameter_names,
            context_parameter_name,
            context_memory_type,
            context_output_type,
        ) = self._resolve_parameters()

        self._validate_context_output_type(context_output_type, produced_type)
        self._validate_self_flow(consumed_parameters, produced_type)

        return DomainNodeSignature(
            function=self._function,
            consumed_parameters=tuple(consumed_parameters),
            context_parameter_name=context_parameter_name,
            context_memory_type=context_memory_type,
            context_output_type=context_output_type,
            produced_type=produced_type,
            sampled_parameter_names=frozenset(sampled_parameter_names),
            collective_parameter_names=frozenset(collective_parameter_names),
        )

    def _iter_declared_parameters(self) -> list[Parameter]:
        parameters = list(self._signature.parameters.values())
        if parameters and parameters[0].name in {"self", "cls"}:
            parameters = parameters[1:]
        return parameters

    def _resolve_parameters(
        self,
    ) -> tuple[
        list[DomainConsumedParameter],
        set[str],
        set[str],
        str | None,
        type | None,
        type | None,
    ]:
        consumed_parameters: list[DomainConsumedParameter] = []
        sampled_parameter_names: set[str] = set()
        collective_parameter_names: set[str] = set()
        context_parameter_name: str | None = None
        context_memory_type: type | None = None
        context_output_type: type | None = None

        for parameter in self._iter_declared_parameters():
            if parameter.kind in (
                Parameter.VAR_POSITIONAL,
                Parameter.VAR_KEYWORD,
            ):
                raise TypeError(
                    f"Node function '{self._function.__name__}' "
                    "cannot declare *args or **kwargs."
                )

            raw_annotation = self._type_hints.get(parameter.name)

            if raw_annotation is None:
                raise TypeError(
                    f"Parameter '{parameter.name}' from node "
                    f"'{self._function.__name__}' must have "
                    "a type annotation."
                )

            annotation, is_sampled, is_collective = self._unwrap_annotated(
                raw_annotation
            )

            if get_origin(annotation) is NodeContext:
                if is_sampled:
                    raise TypeError(
                        f"Node function '{self._function.__name__}' "
                        "cannot declare its NodeContext parameter as "
                        "Sampled -- Sampled applies only to dataflow "
                        "domain artifact parameters."
                    )

                if is_collective:
                    raise TypeError(
                        f"Node function '{self._function.__name__}' "
                        "cannot declare its NodeContext parameter as "
                        "Collective -- Collective applies only to "
                        "dataflow domain artifact parameters."
                    )

                if context_parameter_name is not None:
                    raise TypeError(
                        f"Node function '{self._function.__name__}' "
                        "cannot declare more than one NodeContext parameter."
                    )

                context_parameter_name = parameter.name
                context_memory_type, context_output_type = (
                    self._parse_context_arguments(annotation)
                )
                continue

            consumed_parameters.append((parameter.name, annotation))
            if is_sampled:
                sampled_parameter_names.add(parameter.name)
            if is_collective:
                collective_parameter_names.add(parameter.name)

        return (
            consumed_parameters,
            sampled_parameter_names,
            collective_parameter_names,
            context_parameter_name,
            context_memory_type,
            context_output_type,
        )

    @staticmethod
    def _unwrap_annotated(annotation: object) -> tuple[type, bool, bool]:
        """
        Unwrap `Annotated[T, ...]` down to `T` (Slice 21B), reporting
        whether `Sampled` (`reed.composition.node.sampled.Sampled`) and,
        since Slice MI-H, whether `Collective`
        (`reed.composition.node.collective.Collective`) were present
        among its metadata, independently of each other. Returns
        `(annotation, False, False)` unchanged for any non-`Annotated`
        annotation -- in particular, for `NodeContext[MemoryType,
        OutputType]`, which is a plain generic subscript, never wrapped
        in `Annotated`, so this is a no-op for it and NodeContext
        detection is provably unaffected.

        Declared to return `type`, not `object`: every annotation that
        reaches this method is already one of resolved-type,
        `NodeContext[...]`, or `Annotated[...]` (never an arbitrary
        non-type value) -- an implicit contract this parser already
        relied on before this slice (`get_type_hints`'s own return type
        is `dict[str, Any]`, so `self._type_hints.get(...)` was always
        `Any`, never independently type-checked, before this method
        existed). The `object`-typed parameter is deliberately kept
        precise for the input side; `cast` reflects the pre-existing
        contract on the way out, not a new, unverified assumption.
        """
        if get_origin(annotation) is Annotated:
            underlying_type, *metadata = get_args(annotation)

            if any(marker is Collective for marker in metadata):
                raise TypeError(
                    "`Annotated[T, Collective]` is no longer supported; "
                    "declare the parameter as `Collective[T]` (issue #31)."
                )

            is_collective = any(marker is CollectiveMarker for marker in metadata)

            if is_collective:
                underlying_type = DomainNodeSignatureParser._collective_item_type(
                    underlying_type
                )

            return (
                underlying_type,
                any(marker is Sampled for marker in metadata),
                is_collective,
            )

        return cast(type, annotation), False, False

    @staticmethod
    def _collective_item_type(annotation: object) -> type:
        """
        `Collective[T]` expands to `Annotated[tuple[T, ...],
        CollectiveMarker]`; the artifact the parameter consumes is `T`,
        the item type, so return it.
        """
        arguments = get_args(annotation)

        if (
            get_origin(annotation) is not tuple
            or len(arguments) != 2
            or arguments[1] is not Ellipsis
        ):
            raise TypeError(
                f"`Collective[T]` expands to `tuple[T, ...]`; got {annotation!r}."
            )

        return cast(type, arguments[0])

    def _parse_context_arguments(self, annotation: object) -> tuple[type, type]:
        arguments = get_args(annotation)

        if len(arguments) != 2:
            raise TypeError(
                f"Node function '{self._function.__name__}' must declare "
                "NodeContext with exactly two type arguments: "
                "NodeContext[MemoryType, OutputType]."
            )

        return arguments[0], arguments[1]

    def _validate_context_output_type(
        self,
        context_output_type: type | None,
        produced_type: type,
    ) -> None:
        if context_output_type is None:
            return

        if context_output_type is not produced_type:
            raise TypeError(
                "NodeContext output type must match the return type of "
                f"node '{self._function.__name__}': NodeContext declares "
                f"'{context_output_type!r}' but the function returns "
                f"'{produced_type!r}'."
            )

    def _validate_self_flow(
        self,
        consumed_parameters: list[DomainConsumedParameter],
        produced_type: type,
    ) -> None:
        consumed_types = {parameter_type for _, parameter_type in consumed_parameters}

        if produced_type in consumed_types:
            raise TypeError(
                f"Node function '{self._function.__name__}' cannot "
                "consume and produce the same domain artifact type "
                f"(self-flow): '{produced_type!r}'."
            )
