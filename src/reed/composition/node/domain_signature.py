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
"""

from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, Signature, iscoroutinefunction, signature
from typing import Callable, TypeAlias, get_args, get_origin, get_type_hints

from reed.composition.node.node_context import NodeContext

DomainConsumedParameter: TypeAlias = tuple[str, type]


@dataclass(frozen=True)
class DomainNodeSignature:
    """
    Result of parsing one typed domain function signature.

    This is intentionally not `NodeDescription` (Priority 2) and does not
    use `ArtifactDescriptor` (Priority 3) -- both belong to Slice 1B.
    """

    function: Callable
    consumed_parameters: tuple[DomainConsumedParameter, ...]
    context_parameter_name: str | None
    context_memory_type: type | None
    context_output_type: type | None
    produced_type: type


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

        self._type_hints = get_type_hints(function, globalns=globalns)

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

        produced_type = self._type_hints["return"]

        (
            consumed_parameters,
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
        str | None,
        type | None,
        type | None,
    ]:
        consumed_parameters: list[DomainConsumedParameter] = []
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

            annotation = self._type_hints.get(parameter.name)

            if annotation is None:
                raise TypeError(
                    f"Parameter '{parameter.name}' from node "
                    f"'{self._function.__name__}' must have "
                    "a type annotation."
                )

            if get_origin(annotation) is NodeContext:
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

        return (
            consumed_parameters,
            context_parameter_name,
            context_memory_type,
            context_output_type,
        )

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
