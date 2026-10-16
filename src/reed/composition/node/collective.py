"""
`Collective[T]`: fan-in over every instance of a domain type.

A node parameter declared `Collective[T]` receives every committed instance
of `T` at once, as `tuple[T, ...]`, resolved from the repository when the
node fires (`ArtifactRepository.get_all_artifact_records`).

It is a triggering input whose arrival is the set as a whole (issue #31):
every instance committed at one superstep barrier, in one
`feed_instances()` call, or removed by `remove_instance()`, counts as one
change. A node consuming `Collective[T]` therefore runs once, after every
worker that produces `T` in the same `push()`, and never sees a partial set
(Scatter-Gather; Hohpe & Woolf, *Enterprise Integration Patterns*, 2003).
Inside a feedback loop this holds when the loop's delay is a `Sampled` edge;
see docs/refactor/architecture.md, "Superstep Execution".

History: Slice MI-H introduced the marker as `Annotated[T, Collective]` with
`InputRole.SAMPLED`, because without a barrier every instance committed on its
own. Issue #31 made it triggering and replaced the spelling with
`Collective[T]`, so the declared type matches the value received.
"""

from __future__ import annotations

from typing import Annotated, TypeVar

T = TypeVar("T")


class CollectiveMarker:
    """
    Marker carried in the metadata of `Collective[T]`.

    Never constructed; recognized by identity in the metadata tuple of
    `Annotated[tuple[T, ...], CollectiveMarker]`.
    """


Collective = Annotated[tuple[T, ...], CollectiveMarker]
"""
`Collective[T]`: a consumed node parameter that receives every instance of
`T` at once, as `tuple[T, ...]` (fan-in).

It is a generic alias of `Annotated` (PEP 593, "Aliases & Concerns over
verbosity"): a type checker sees exactly the value the node receives,
`tuple[T, ...]`, and Reed reads `CollectiveMarker` from the metadata. The
same convention LangGraph uses for state reducers, where
`Annotated[list[str], operator.add]` keeps the real type visible and puts
the behavior in the metadata (LangGraph docs, "Graph API overview",
Reducers).
"""
