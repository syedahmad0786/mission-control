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

## Public deployment verification

- Live URL: https://agentops-mission-control.vercel.app
- Runtime commit: `edf07e46115d9367f6485790b5b268e05be5026f`
- GitHub CI: pass
- Postman CLI against the commit-specific preview: 4 requests and 11 assertions, 0 failures
- Browser journeys: 1280×800 and 390×844, 0 console errors and 0 horizontal overflow
- Release: the tested preview artifact was promoted without rebuilding
