"""
Public `reed.flow` module (Slice 1F).

Re-exports `FlowNode` so the target composition API's
`from reed.flow import FlowNode` shape
(docs/flow_composition_implementation_basis.md) works. This is a thin
top-level module distinct from the `reed.composition.flow` implementation
package (a different dotted path -- no collision): the implementation
lives under `reed.composition.flow.flow_node`, this module only re-exports
its public name.
"""

from __future__ import annotations

from reed.composition.flow.flow_node import FlowNode

__all__ = ["FlowNode"]
