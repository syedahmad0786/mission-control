# AgentOps Mission Control — Evaluation Report

**Evaluation mode:** deterministic replay  
**Data:** synthetic, versioned fixtures  
**Last local result:** 3 tests passed on Python 3.12

| Scenario | Expected | Observed | Result |
|---|---|---|---|
| `healthy` | No incident | No incident | Pass |
| `failed` | Failed incident | Failed incident | Pass |
| `slow` | Latency incident | Latency incident | Pass |
| `stale` | Staleness incident | Staleness incident | Pass |
| `over_budget` | Budget incident | Budget incident | Pass |
| `approval_bottleneck` | Stale plus approval incidents | Both incidents | Pass |

Boundary checks passed for idempotent replay, conflicting input rejection, ordered timestamps, bounded cost, bounded steps, and zero external mutations. OpenTelemetry also remains safe when no exporter is configured.

Preview Postman, browser, and deployment checks are recorded here only after a commit-specific Vercel preview passes them.
