"""Deterministic telemetry analysis for AgentOps Mission Control."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing() -> None:
    """Export OTLP spans when configured; otherwise stay zero-config."""
    if not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "agentops-mission-control"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)


configure_tracing()
TRACER = trace.get_tracer(__name__)


class EvidenceRef(BaseModel):
    source: str
    locator: str
    retrieved_at: datetime
    content_hash: str


class TelemetryRun(BaseModel):
    run_id: str = Field(min_length=1, max_length=120)
    system: str = Field(min_length=1, max_length=120)
    status: Literal["success", "failed", "running", "waiting_approval"]
    started_at: datetime
    updated_at: datetime
    latency_ms: int = Field(ge=0, le=90000)
    budget_usd: float = Field(ge=0, le=1000)
    cost_usd: float = Field(ge=0, le=1000)
    steps: int = Field(ge=0, le=12)
    approvals_pending: int = Field(default=0, ge=0, le=20)
    error: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> "TelemetryRun":
        if self.updated_at < self.started_at:
            raise ValueError("updated_at must be on or after started_at")
        return self


class RunRequest(BaseModel):
    scenario: Literal[
        "healthy", "failed", "slow", "stale", "over_budget", "approval_bottleneck", "custom"
    ] = "healthy"
    input: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["replay", "live"] = "replay"
    idempotency_key: str = Field(min_length=8, max_length=120)


class Incident(BaseModel):
    code: Literal["failed", "slow", "stale", "over_budget", "approval_bottleneck"]
    severity: Literal["critical", "high", "medium"]
    summary: str
    evidence: list[str]
    impact: str
    confidence: float = Field(ge=0, le=1)
    suggested_owner: str


class UsageRecord(BaseModel):
    model: str = "deterministic/replay"
    tokens: int = 0
    latency_ms: int
    estimated_cost_usd: float = 0


class RunRecord(BaseModel):
    run_id: str
    status: Literal["completed"] = "completed"
    scenario: str
    mode: str
    created_at: datetime
    input_hash: str
    agent_steps: list[dict[str, Any]]
    outputs: dict[str, Any]
    evidence: list[EvidenceRef]
    usage: UsageRecord
    errors: list[str] = Field(default_factory=list)


class IdempotencyConflict(ValueError):
    pass


_RUNS: dict[str, RunRecord] = {}
_KEYS: dict[str, str] = {}


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def replay_telemetry(scenario: str, now: datetime | None = None) -> list[TelemetryRun]:
    now = now or datetime.now(UTC)
    base = {
        "run_id": f"seed-{scenario}",
        "system": "portfolio-research-agent",
        "status": "success",
        "started_at": now - timedelta(seconds=4),
        "updated_at": now,
        "latency_ms": 3900,
        "budget_usd": 0.05,
        "cost_usd": 0.018,
        "steps": 7,
        "approvals_pending": 0,
    }
    changes: dict[str, dict[str, Any]] = {
        "healthy": {},
        "failed": {"status": "failed", "error": "tool timeout after final retry"},
        "slow": {"latency_ms": 11800},
        "stale": {
            "status": "running",
            "started_at": now - timedelta(minutes=18),
            "updated_at": now - timedelta(minutes=12),
        },
        "over_budget": {"cost_usd": 0.091},
        "approval_bottleneck": {
            "status": "waiting_approval",
            "started_at": now - timedelta(minutes=28),
            "updated_at": now - timedelta(minutes=16),
            "approvals_pending": 3,
        },
    }
    return [TelemetryRun.model_validate(base | changes.get(scenario, {}))]


def analyze_telemetry(runs: list[TelemetryRun], now: datetime | None = None) -> list[Incident]:
    now = now or datetime.now(UTC)
    incidents: list[Incident] = []
    for run in runs:
        if run.status == "failed":
            incidents.append(Incident(
                code="failed", severity="critical",
                summary=f"{run.system} ended in failure",
                evidence=[f"status={run.status}", f"error={run.error or 'not supplied'}"],
                impact="The requested outcome was not produced.", confidence=1,
                suggested_owner="agent operations",
            ))
        if run.latency_ms > 5000:
            incidents.append(Incident(
                code="slow", severity="medium",
                summary=f"{run.system} exceeded the 5 second latency target",
                evidence=[f"latency_ms={run.latency_ms}", "target_ms=5000"],
                impact="Users wait longer and serverless timeout risk increases.", confidence=1,
                suggested_owner="platform",
            ))
        age = now - run.updated_at
        if run.status in {"running", "waiting_approval"} and age > timedelta(minutes=10):
            incidents.append(Incident(
                code="stale", severity="high",
                summary=f"{run.system} has made no progress for {int(age.total_seconds() // 60)} minutes",
                evidence=[f"status={run.status}", f"last_update={run.updated_at.isoformat()}"],
                impact="Work may be stranded and require replay or human intervention.", confidence=1,
                suggested_owner="agent operations",
            ))
        if run.budget_usd and run.cost_usd > run.budget_usd:
            incidents.append(Incident(
                code="over_budget", severity="high",
                summary=f"{run.system} exceeded its run budget",
                evidence=[f"cost_usd={run.cost_usd:.3f}", f"budget_usd={run.budget_usd:.3f}"],
                impact="Unbounded inference spend can make the workflow uneconomic.", confidence=1,
                suggested_owner="AI operations",
            ))
        if run.approvals_pending > 0:
            incidents.append(Incident(
                code="approval_bottleneck", severity="medium",
                summary=f"{run.approvals_pending} approvals are blocking {run.system}",
                evidence=[f"approvals_pending={run.approvals_pending}", f"status={run.status}"],
                impact="The run cannot safely advance until an accountable person decides.", confidence=1,
                suggested_owner="business approver",
            ))
    return incidents


def _execute(request: RunRequest) -> RunRecord:
    payload_hash = _hash(request.model_dump(mode="json"))
    existing_id = _KEYS.get(request.idempotency_key)
    if existing_id:
        existing = _RUNS[existing_id]
        if existing.input_hash != payload_hash:
            raise IdempotencyConflict("idempotency key was already used for different input")
        return existing

    if request.scenario == "custom":
        raw_runs = request.input.get("runs")
        if not isinstance(raw_runs, list) or not raw_runs:
            raise ValueError("custom scenario requires input.runs")
        telemetry = [TelemetryRun.model_validate(item) for item in raw_runs]
    else:
        telemetry = replay_telemetry(request.scenario)

    incidents = analyze_telemetry(telemetry)
    run_id = f"run_{payload_hash[:16]}"
    source_hash = _hash([item.model_dump(mode="json") for item in telemetry])
    record = RunRecord(
        run_id=run_id,
        scenario=request.scenario,
        mode=request.mode,
        created_at=datetime.now(UTC),
        input_hash=payload_hash,
        agent_steps=[
            {"agent": "telemetry-normalizer", "status": "completed", "records": len(telemetry)},
            {"agent": "incident-detector", "status": "completed", "incidents": len(incidents)},
            {"agent": "operations-reporter", "status": "completed", "mutations": 0},
        ],
        outputs={
            "incidents": [item.model_dump(mode="json") for item in incidents],
            "summary": f"{len(incidents)} incident(s) found across {len(telemetry)} telemetry run(s)",
            "mutations_performed": 0,
        },
        evidence=[EvidenceRef(
            source="submitted telemetry" if request.scenario == "custom" else "versioned replay fixture",
            locator=f"scenario:{request.scenario}",
            retrieved_at=datetime.now(UTC),
            content_hash=source_hash,
        )],
        usage=UsageRecord(latency_ms=1),
    )
    _KEYS[request.idempotency_key] = run_id
    _RUNS[run_id] = record
    return record


def execute(request: RunRequest) -> RunRecord:
    with TRACER.start_as_current_span("agentops.analyze") as span:
        span.set_attribute("portfolio.scenario", request.scenario)
        span.set_attribute("portfolio.mode", request.mode)
        record = _execute(request)
        span.set_attribute("portfolio.incident_count", len(record.outputs["incidents"]))
        return record


def get_run(run_id: str) -> RunRecord | None:
    return _RUNS.get(run_id)
