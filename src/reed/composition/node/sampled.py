"""
Sampled marker (Slice 21B, GitHub issue #21 -- "Distinguish triggering
inputs from sampled inputs in node firing rules").

Scope (GitHub issue #21):

    A node declares a consumed parameter as sampled -- contributing to
    the node's argument coverage but never, by itself, to its firing
    eligibility (see `reed.composition.node.artifact_descriptor.InputRole`,
    `Session._is_eligible_to_fire`, Slice 21C) -- by annotating it
    `Annotated[T, Sampled]` instead of plain `T`.

`Sampled` is detected by annotation shape, the same principle already
established for `NodeContext[MemoryType, OutputType]`
(`node_context_decision.md`'s "Context Injection Rule": "Reed should
detect NodeContext[...] by type annotation... the semantic rule should
be based on the annotation, not only on parameter position"). It is
never instantiated: it exists only as the second argument to
`typing.Annotated[T, Sampled]`, detected in
`reed.composition.node.domain_signature.DomainNodeSignatureParser` via
`typing.get_type_hints(..., include_extras=True)` plus
`typing.get_origin(annotation) is Annotated` /
`typing.get_args(annotation)`.

This module's own placement (a dedicated module per concept, mirroring
`node_context.py`) is a Slice 21B naming decision recorded in this
slice's SliceContract `stop_conditions`, not one grounded in any
surviving accepted document.
"""

from __future__ import annotations


class Sampled:
    """
    Marker for `Annotated[T, Sampled]` on a consumed node parameter.

    Carries no state and is never constructed; its only role is to be
    recognized, by identity, in the metadata tuple of an `Annotated[...]`
    type hint.
    """
