"""
Focused tests for Slice 2A (Flow / Session separation), including the Slice
2A follow-up correcting Session-scoped repository ownership.

No target-architecture-contract test is expected to move for this slice
or this follow-up (docs/refactor_priority_order.md's Slice 2A row: "No
target test moves alone"; confirmed by reading every one of the six
remaining xfail tests in tests/test_target_architecture_contract.py --
all six require NodeSession/commit semantics/callback dispatch/stateful
serialization, none of which exist yet). This file is Slice 2A's
dedicated focused verification, following the same rationale used for
Slices 1A/1B/1C/1D.

Covers exactly the five architectural properties the harness assigned to
the original slice, plus the corrected repository-ownership contract
added by the follow-up:

    1. Flow.session() returns a Session.
    2. Two Flow.session() calls return distinct Session instances.
    3. Session is associated with the originating Flow.
    4. Flow remains reusable (no error, no shared mutable state leak,
       across repeated session() calls, and Flow.add(...) still works
       normally after session() has been called).
    5. Session-specific state is not stored on Flow.
    6. Each Session owns its own repository instance, backed by ArtifactRepository, and
       two Sessions never share repository state or repository identity.
"""

from __future__ import annotations


def test_flow_session_returns_a_session():
    from reed import Flow
    from reed.execution.session import Session

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    session = flow.session()

    assert isinstance(session, Session)


def test_two_flow_session_calls_return_distinct_session_instances():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_session = flow.session()
    second_session = flow.session()

    assert first_session is not second_session


def test_session_is_associated_with_the_originating_flow():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    session = flow.session()

    assert session.flow is flow


def test_distinct_flows_produce_sessions_associated_with_their_own_flow():
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b() -> str:
        return "b"

    flow_a = Flow()
    flow_a.add(produce_a)

    flow_b = Flow()
    flow_b.add(produce_b)

    session_a = flow_a.session()
    session_b = flow_b.session()

    assert session_a.flow is flow_a
    assert session_b.flow is flow_b
    assert session_a.flow is not session_b.flow


def test_flow_remains_reusable_across_multiple_sessions():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    sessions = [flow.session() for _ in range(5)]

    assert len({id(r) for r in sessions}) == 5
    assert all(r.flow is flow for r in sessions)


def test_flow_add_still_works_after_session_has_been_called():
    # Flow must remain a usable composition object after session() -- calling
    # session() must not put Flow into some execution-only state.
    from reed import Flow

    def produce_a() -> int:
        return 1

    def produce_b() -> str:
        return "b"

    flow = Flow()
    flow.add(produce_a)
    flow.session()

    flow_node = flow.add(produce_b)

    assert flow_node.produced_artifact.domain_type is str


def test_flow_instance_state_is_unchanged_by_session():
    # Flow-owns-no-Session-specific-state, verified structurally: calling
    # session() (repeatedly) must not add or mutate any attribute on the
    # Flow instance itself.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))

    flow.session()
    flow.session()
    flow.session()

    after = dict(vars(flow))

    assert before.keys() == after.keys()
    for key in before:
        assert before[key] is after[key], (
            f"Flow.{key} changed identity after calling session() -- "
            "Flow must own no Session-specific mutable state"
        )


def test_session_publish_capability_was_removed():
    # Slice 2E legitimately added Session.publish as the real firing entry
    # point, which made this test's original negative assertion
    # (not hasattr(session, "publish")) stale by construction, and it was
    # flipped in place to a positive assertion -- the same Test Integrity
    # Rule precedent already applied in Slices 2B and 2D (see
    # docs/refactor_state.md). Slice 22H-2 has now deleted
    # Session.publish()/publish_many() entirely (issue #22's target public
    # API is Flow.add/session()/feed()/push()/snapshot()/invoke(), per
    # docs/refactor/session_snapshot_decision.md section 2), which makes
    # that positive assertion stale by construction in turn -- flipped back
    # here, renamed to describe what it now actually checks, following the
    # same precedent (also used in this issue's own 22C/22F test rewrites).
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    assert not hasattr(session, "publish")


# --- Slice 2A follow-up: Session-scoped repository ownership -------------------


def test_session_has_a_repository_accessor():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    assert hasattr(session, "repository")
    assert session.repository is not None


def test_session_repository_is_backed_by_artifact_repository():
    from reed import Flow
    from reed.synchronization.artifact_repository import ArtifactRepository

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)
    session = flow.session()

    assert isinstance(session.repository, ArtifactRepository)


def test_each_session_owns_a_distinct_repository_instance():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_session = flow.session()
    second_session = flow.session()

    assert first_session.repository is not second_session.repository


def test_two_sessions_from_the_same_flow_do_not_share_repository_identity():
    # ArtifactRepository.identity is derived from the Bus it was constructed with;
    # two Sessions must each construct their own Bus, so their repositories'
    # identities must differ even though both Sessions came from one Flow.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    first_session = flow.session()
    second_session = flow.session()

    assert first_session.repository.identity != second_session.repository.identity


def test_flow_does_not_own_the_repository():
    # Repository ownership belongs to Session, not Flow -- Flow's own
    # instance state must still contain nothing Session-specific, repository
    # included.
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    before = dict(vars(flow))
    flow.session()
    after = dict(vars(flow))

    assert before.keys() == after.keys()
    assert not hasattr(flow, "repository")
    assert not hasattr(flow, "_repository")


def test_repeated_flow_session_calls_remain_independent_with_distinct_repositories():
    from reed import Flow

    def produce() -> int:
        return 1

    flow = Flow()
    flow.add(produce)

    sessions = [flow.session() for _ in range(5)]

    repository_identities = {session.repository.identity for session in sessions}
    assert len(repository_identities) == 5
