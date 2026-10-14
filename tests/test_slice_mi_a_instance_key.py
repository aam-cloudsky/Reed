"""
Slice MI-A: InstanceKey, an additive domain-artifact-instance identity
primitive (docs/refactor/multi_instance_execution_plan.md, Section 5).

Purely additive: these tests exercise InstanceKey in isolation. Nothing
here touches ArtifactRepository, ArtifactProvenance, or Session -- wiring
those is out of scope for this slice (see the slice's own SliceContract,
.claude/reed-refactor/run-MI-A-20260925T163526Z/slice_contract.yaml).
"""

import pytest

from reed.execution.instance_key import InstanceKey


def test_instance_key_equal_for_same_wrapped_value():
    assert InstanceKey(key="A") == InstanceKey(key="A")


def test_instance_key_not_equal_for_different_wrapped_value():
    assert InstanceKey(key="A") != InstanceKey(key="B")


def test_instance_key_is_hashable_and_usable_as_dict_key():
    by_key = {
        InstanceKey(key="A"): "first",
        InstanceKey(key="B"): "second",
    }

    assert by_key[InstanceKey(key="A")] == "first"
    assert by_key[InstanceKey(key="B")] == "second"
    assert hash(InstanceKey(key="A")) == hash(InstanceKey(key="A"))


def test_instance_key_singleton_is_stable_across_calls():
    assert InstanceKey.singleton() == InstanceKey.singleton()
    assert hash(InstanceKey.singleton()) == hash(InstanceKey.singleton())


def test_instance_key_singleton_is_distinct_from_a_domain_value_key():
    assert InstanceKey.singleton() != InstanceKey(key="A")
    assert InstanceKey.singleton() != InstanceKey(key="singleton")


def test_instance_key_is_frozen():
    key = InstanceKey(key="A")

    with pytest.raises(Exception):
        key.key = "B"
