"""FastAPI portfolio surface; the original Streamlit scanner remains in app.py."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from agentops import IdempotencyConflict, RunRecord, RunRequest, execute, get_run

app = FastAPI(
    title="AgentOps Mission Control",
    version="1.0.0",
    description="Replay-first telemetry analysis with deterministic incident gates.",
)

_RATE: dict[tuple[str, date], int] = defaultdict(int)


def _limit(request: Request) -> None:
    key = ((request.headers.get("x-forwarded-for") or request.client.host).split(",")[0], date.today())
    _RATE[key] += 1
    if _RATE[key] > 5:
        raise HTTPException(429, "Public demo limit reached: five runs per IP per day")


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.now(UTC), "mode": "replay-ready"}


@app.get("/api/v1/capabilities")
def capabilities() -> dict:
    return {
        "system": "AgentOps Mission Control",
        "detects": ["failed", "slow", "stale", "over_budget", "approval_bottleneck"],
        "modes": ["replay", "live telemetry input"],
        "limits": {"runs_per_ip_day": 5, "max_steps": 12, "max_agents": 3, "timeout_seconds": 90},
        "mutations": False,
    }


@app.post("/api/v1/telemetry/runs", response_model=RunRecord)
def ingest(payload: RunRequest, request: Request) -> RunRecord:
    _limit(request)
    try:
        return execute(payload)
    except IdempotencyConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/v1/runs/{run_id}", response_model=RunRecord)
def run(run_id: str) -> RunRecord:
    record = get_run(run_id)
    if not record:
        raise HTTPException(404, "Run not found in this demo instance")
    return record


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgentOps Mission Control</title><style>
:root{--ink:#091421;--panel:#0e2033;--line:#25425b;--signal:#ffb448;--calm:#8fd6c7;--paper:#e7eef3;--muted:#91a6b7}
*{box-sizing:border-box}body{margin:0;background:var(--ink);color:var(--paper);font-family:Segoe UI,Arial,sans-serif}
main{max-width:1100px;margin:auto;padding:32px 22px 64px}.kicker,.label{font:700 12px/1.3 Consolas,monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--calm)}
h1{max-width:820px;margin:12px 0;font:650 clamp(42px,8vw,88px)/.92 Georgia,serif;letter-spacing:-.055em}.intro{max-width:670px;color:var(--muted);font-size:17px;line-height:1.6}
.scope{margin:34px 0;border-block:1px solid var(--line);display:grid;grid-template-columns:repeat(3,1fr)}.scope div{padding:18px;border-right:1px solid var(--line)}.scope div:last-child{border:0}.scope strong{display:block;font:600 23px Consolas,monospace;color:var(--signal)}
.console{display:grid;grid-template-columns:330px 1fr;border:1px solid var(--line);background:var(--panel);box-shadow:16px 16px 0 #07101a}.controls{padding:24px;border-right:1px solid var(--line)}label{display:block;margin-bottom:8px}.hint{color:var(--muted);font-size:13px;line-height:1.5}select,button{width:100%;border:1px solid var(--line);border-radius:0;padding:13px;background:#091827;color:var(--paper);font:600 15px Segoe UI}button{margin-top:12px;background:var(--signal);color:#1c1407;border-color:var(--signal);cursor:pointer}button:focus-visible,select:focus-visible{outline:3px solid var(--calm);outline-offset:2px}
.screen{min-height:360px;padding:24px;background-image:linear-gradient(rgba(143,214,199,.035) 1px,transparent 1px);background-size:100% 32px}.empty{color:var(--muted);margin-top:110px;text-align:center}.incident{border-left:4px solid var(--signal);padding:14px 16px;margin:0 0 12px;background:#0a1826}.incident h3{margin:3px 0 7px;font-size:18px}.incident p{margin:0;color:var(--muted);line-height:1.45}.critical{border-color:#ff6b6b}.high{border-color:#ffb448}.medium{border-color:#8fd6c7}.summary{font:700 13px Consolas,monospace;color:var(--calm);margin-bottom:18px}
.foot{margin-top:24px;color:var(--muted);font-size:13px}code{color:var(--calm)}@media(max-width:720px){main{padding:24px 16px}.scope{grid-template-columns:1fr}.scope div{border-right:0;border-bottom:1px solid var(--line)}.console{grid-template-columns:1fr;box-shadow:8px 8px 0 #07101a}.controls{border-right:0;border-bottom:1px solid var(--line)}.screen{min-height:320px}.empty{margin-top:70px}}
@media(prefers-reduced-motion:no-preference){.incident{animation:land .28s ease-out both}@keyframes land{from{opacity:0;transform:translateY(8px)}}}
</style></head><body><main>
<div class="kicker">Portfolio system 01 · deterministic agent operations</div><h1>See the failure before it becomes folklore.</h1>
<p class="intro">AgentOps Mission Control turns run telemetry into evidence-backed incidents. Deterministic gates decide what failed; reporting agents explain impact. Nothing mutates an external system.</p>
<section class="scope"><div><strong>5</strong><span class="label">failure signals</span></div><div><strong>0</strong><span class="label">autonomous mutations</span></div><div><strong>100%</strong><span class="label">replayable demos</span></div></section>
<section class="console"><div class="controls"><label class="label" for="scenario">Seeded telemetry</label><select id="scenario"><option value="failed">Failed run</option><option value="slow">Slow run</option><option value="stale">Stale run</option><option value="over_budget">Over budget</option><option value="approval_bottleneck">Approval bottleneck</option><option value="healthy">Healthy run</option></select><button id="run">Analyze telemetry</button><p class="hint">Replay fixtures contain no client data and use no paid model. The API contract is available at <code>/docs</code>.</p></div><div class="screen" id="screen"><p class="empty">Choose a signal and run the detector.</p></div></section>
<p class="foot">Agentic AI &amp; LLM Systems Specialist · Ahmad Bukhari</p></main><script>
const screen=document.querySelector('#screen'),button=document.querySelector('#run');
button.addEventListener('click',async()=>{button.disabled=true;button.textContent='Analyzing…';screen.innerHTML='<p class="empty">Normalizing telemetry → applying incident gates → drafting report</p>';try{const scenario=document.querySelector('#scenario').value;const response=await fetch('/api/v1/telemetry/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({scenario,input:{},mode:'replay',idempotency_key:`demo-${scenario}-0001`})});const data=await response.json();if(!response.ok)throw new Error(data.detail||'Run failed');const incidents=data.outputs.incidents;screen.innerHTML=`<div class="summary">${data.outputs.summary} · ${data.run_id}</div>`+(incidents.length?incidents.map((item)=>`<article class="incident ${item.severity}"><span class="label">${item.severity} · ${item.code.replaceAll('_',' ')}</span><h3>${item.summary}</h3><p>${item.impact}</p></article>`).join(''):'<article class="incident medium"><span class="label">clear</span><h3>No incident threshold was crossed</h3><p>The replay run stayed inside its latency, cost, freshness, and approval targets.</p></article>');}catch(error){screen.innerHTML=`<p class="empty">${error.message}</p>`}finally{button.disabled=false;button.textContent='Analyze telemetry'}});
</script></body></html>'''


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> str:
    return PAGE
