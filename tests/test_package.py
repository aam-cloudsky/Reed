from __future__ import annotations

import pytest


def test_public_api_exports_current_architecture_symbols():
    import reed

    assert reed.Flow is not None
    assert reed.TriggerPolicy is not None
    assert reed.NodeContext is not None
    assert reed.Run is not None


def test_public_api_exports_exactly_the_current_architecture_symbols():
    import reed

    assert set(reed.__all__) == {"Flow", "TriggerPolicy", "NodeContext", "Run"}


@pytest.mark.parametrize(
    "retired_symbol",
    ["Parcel", "node", "output", "input"],
)
def test_retired_legacy_symbols_are_no_longer_public(retired_symbol):
    """
    Issue #4 finalization: the previous decorator/Parcel programming
    model is retired, not merely undocumented. These names must not be
    importable from the top-level `reed` package at all.

    ("flow" is deliberately excluded from this list: `reed.flow` is a
    legitimate, still-current submodule -- see
    test_reed_flow_submodule_is_not_the_retired_decorator below -- not
    the retired `@flow` decorator. A bare `from reed import flow`
    resolves to that submodule via Python's ordinary package-submodule
    import machinery, which is correct behavior, not a compatibility
    leak.)
    """
    import reed

    assert not hasattr(reed, retired_symbol)

    with pytest.raises(ImportError):
        exec(f"from reed import {retired_symbol}")


def test_reed_flow_submodule_is_not_the_retired_decorator():
    """
    `reed.flow` is the current architecture's `FlowNode` re-export
    (`from reed.flow import FlowNode`), not the retired `@flow` class
    decorator. It is a module, not a callable.
    """
    import reed.flow as flow_module

    assert not callable(flow_module)
    assert flow_module.FlowNode is not None
    assert set(flow_module.__all__) == {"FlowNode"}


def test_retired_legacy_modules_are_gone():
    """
    The legacy decorator module, and the legacy Flow/Node composition
    modules it depended on, must no longer exist at all -- not just be
    unreferenced from the public package.
    """
    import importlib

    for module_name in [
        "reed.api.decorator",
        "reed.composition.flow.flow",
        "reed.composition.flow.flow_definition",
        "reed.composition.flow.flow_factory",
        "reed.composition.node.node",
        "reed.composition.node.node_builder",
        "reed.composition.node.node_definition",
        "reed.composition.node.propagation_policy",
        "reed.synchronization.parcel.parcel",
        "reed.synchronization.parcel.provenance",
        "reed.synchronization.logistics",
        "reed.synchronization.repository_adapter",
        "reed.synchronization.repository_adapter_builder",
        "reed.synchronization.validity.dependency_registry",
        "reed.synchronization.validity.repository_adapter_sentinel",
        "reed.synchronization.validity.repository_adapter_validity_transition",
        "reed.activation.status.repository_adapter_status",
        "reed.activation.status.repository_adapter_status_manager",
        "reed.activation.status.repository_adapter_dirty_flags",
        "reed.activation.schema",
        "reed.activation.dependency_descriptor",
        "reed.exceptions.errors",
        "reed.transportation.protocol.validity_message",
        "reed.synchronization.artifact_repository_messages",
    ]:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
