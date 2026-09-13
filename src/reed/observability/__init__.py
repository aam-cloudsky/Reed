"""
Reed observability foundations (Issue #7, Milestone O1 -- Identity
Foundations).

This package is deliberately separate from `reed.transportation.observability`,
which is the pre-Issue-4 Bus/Depot/Outpost-era tracing machinery
(`docs/observability_non_goals.md` Section 9: do not revive or extend it).
Nothing in this package imports from, or is imported by, that legacy
package.

See `docs/observability_design.md`, `docs/observability_goals.md`, and
`docs/observability_harness.md` for the architecture this package
implements incrementally, slice by slice.
"""

from __future__ import annotations
