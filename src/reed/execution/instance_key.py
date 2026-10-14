"""
InstanceKey (Slice MI-A, issue "Support multiple artifact instances and
per-instance node execution"; see
docs/refactor/multi_instance_execution_plan.md, Section 1.1/1.2 for the
diagnosis this responds to, and Section 5 for this slice's own scope).

`ArtifactRepository` (`src/reed/synchronization/artifact_repository.py`),
`ArtifactProvenance` (`src/reed/execution/artifact_record.py`), and
`Session` (`src/reed/execution/session.py`) today address a committed
artifact purely by its domain type. `InstanceKey` is the additive
primitive later slices (MI-B onward) key their own storage on, alongside
the existing type key, never in place of it: a repository entry becomes
addressable by (domain type, InstanceKey) once MI-B wires this in, not by
InstanceKey alone.

This slice is deliberately narrow, matching the pattern already used for
`ArtifactDescriptor` (Slice 1B) and `InputRole` (Slice 21A): a plain value
type, additive, with nothing elsewhere in the repository, provenance
model, or session execution path constructing or reading one yet. Wiring
InstanceKey into `ArtifactRepository`, `ArtifactProvenance.dependencies`,
or `Session`'s eligibility bookkeeping is explicitly out of scope here
(MI-B through MI-J; see the plan document's Section 5) -- this file is
not imported by any of them.

`InstanceKey` is not part of Reed's public package surface
(`src/reed/__init__.py`) yet. Whether a caller of the eventual multi-
instance `Session.feed(...)` constructs an `InstanceKey` directly, or
supplies a plain domain identity value Reed wraps internally, is a public-
API decision for a later slice (MI-D, `Session.feed()` accepting multiple
instances), not this one.
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass


@dataclass(frozen=True)
class InstanceKey:
    """
    One domain artifact instance's identity, distinct from its domain
    type.

    Wraps a single `Hashable` value. Two `InstanceKey`s are equal, and
    hash equal, exactly when their wrapped `key` values are equal and
    hash equal (the dataclass-generated `__eq__`/`__hash__`, over the one
    field). Python's own hashing contract governs `key` the same way it
    already governs every other dict key or set member in this codebase:
    nothing here validates hashability eagerly at construction, since
    Reed does not do so anywhere else either (for example,
    `ArtifactRepository`'s existing `dict[type, ArtifactRecord]` never
    validates that a `type` is hashable -- it simply is). An unhashable
    `key` surfaces the ordinary Python `TypeError` at the point of actual
    use (hashing, or insertion into a dict/set), not here.
    """

    key: Hashable

    @classmethod
    def singleton(cls) -> "InstanceKey":
        """
        The implicit instance identity every existing, pre-multiplicity
        commit path is understood to address once a later slice wires
        this key in as every current call site's default (docs/refactor/
        multi_instance_execution_plan.md, Risk R1 and R7): a stable,
        reserved key, backed by a private module-level sentinel object,
        distinct from any value a caller would plausibly pass as a real
        instance identity to the future multi-instance form of
        `Session.feed(...)`.

        Returns the same `InstanceKey` value (equal, and hash-equal, to
        any other `InstanceKey.singleton()`) on every call -- the
        sentinel is a module-level singleton object, not re-created per
        call, so `InstanceKey.singleton() == InstanceKey.singleton()` and
        both are usable interchangeably as the same dict key.
        """
        return cls(key=_SINGLETON_SENTINEL)


class _InstanceKeySingletonSentinel:
    """
    A private, unique sentinel object identifying the implicit "no real
    multiplicity" instance. Not a domain value any caller could construct
    or accidentally collide with: it is never exposed, only ever reached
    through `InstanceKey.singleton()`.
    """

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return "<InstanceKey.singleton>"


_SINGLETON_SENTINEL = _InstanceKeySingletonSentinel()
