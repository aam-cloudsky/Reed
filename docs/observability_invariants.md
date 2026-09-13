# Reed Observability — Architectural Invariants

## Identity

1. `execution_id` uniquely identifies one Execution.
2. `node_execution_id` uniquely identifies one Node firing.
3. `flow_id` identifies the logical Flow across Executions.
4. `node_id` identifies a logical Node within a Flow across Executions.
5. `node_name` is presentation metadata, never identity.
6. Reed IDs are independent of OpenTelemetry IDs.

## Ordering and causality

7. `execution_seq` provides deterministic observation ordering only.
8. `execution_seq` never represents causality.
9. Causality is represented explicitly through execution/provenance relationships.

## Instruments and recordings

10. Instrument is the logical unit of observation.
11. Execution is the physical persistence boundary.
12. Flow is the logical aggregation boundary.
13. `ctx.record()` is backend-agnostic.
14. `ctx.record()` contains application-declared observations only.
15. Recording values are scalar.
16. Instrument definitions are immutable once established.

## Persistence

17. Each Execution owns its physical Recording and Provenance stores.
18. No physical Recording store is shared between Executions.
19. Physical partitioning is an implementation detail behind the store abstraction.
20. The durability boundary is NodeExecution exit.
21. A hard process failure before that boundary may lose the in-flight batch.

## Provenance

22. Artifact generation and usage are distinct provenance events.
23. Artifact provenance and execution ordering are independent concepts.
24. Each Artifact type has exactly one producer within a Flow.

## Isolation

25. Observability failures must never change application semantics.
26. Remote exporters are never on the Node hot path.
27. OpenTelemetry is an optional projection, not Reed's source of truth.