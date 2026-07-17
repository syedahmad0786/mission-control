"""mission-control scanner — reads every project's artifacts in place.

No agents were modified to build this: each project already leaves evidence
on disk (digests, briefs, queues, run histories, indexes). The scanner knows
where to look and turns it into one uniform status feed.

Stdlib only, so the dashboard has zero heavy dependencies for data.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(os.getenv("MISSION_ROOT", Path(__file__).resolve().parent.parent))

FRESH_H, RECENT_D = 24, 7


@dataclass
class Status:
    name: str
    tier: str                 # "business" | "paper"
    purpose: str
    metric: str = "—"
    last_ts: float | None = None
    artifacts: list[str] = field(default_factory=list)
    verified: bool = False

    @property
    def state(self) -> str:
        if self.last_ts is None:
            return "never run"
        age_h = (time.time() - self.last_ts) / 3600
        if age_h <= FRESH_H:
            return "fresh"
        if age_h <= RECENT_D * 24:
            return "recent"
        return "idle"

    @property
    def last_human(self) -> str:
        if self.last_ts is None:
            return "—"
        age = time.time() - self.last_ts
        if age < 3600:
            return f"{int(age // 60)}m ago"
        if age < 86400:
            return f"{int(age // 3600)}h ago"
        return f"{int(age // 86400)}d ago"


# ------------------------------------------------------------------ helpers #
def _mtime(*paths: Path) -> float | None:
    stamps = [p.stat().st_mtime for p in paths if p.exists()]
    return max(stamps) if stamps else None


def _glob_latest(folder: Path, pattern: str) -> tuple[float | None, list[str]]:
    files = sorted(folder.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True) \
        if folder.exists() else []
    return (files[0].stat().st_mtime if files else None,
            [f.name for f in files[:5]])


def _sq(db: Path, query: str):
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        row = conn.execute(query).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------- probes #
def _probe(name: str, tier: str, purpose: str) -> Status:
    p = ROOT / name
    s = Status(name=name, tier=tier, purpose=purpose)
    if not p.exists():
        s.metric = "not found"
        return s

    if name == "flowsentry":
        ts = _mtime(p / "digest.md")
        if ts:
            text = (p / "digest.md").read_text(encoding="utf-8", errors="ignore")
            crit = text.count("🔴")
            warn = text.count("🟡")
            s.metric = f"last digest: {crit} critical · {warn} warnings"
            s.artifacts = ["digest.md"]
        s.last_ts = ts

    elif name == "salescout-agents":
        ts, files = _glob_latest(p / "briefs", "*.md")
        s.metric = f"{len(list((p/'briefs').glob('*.md')))} briefs" if (p/'briefs').exists() else "no briefs yet"
        s.last_ts, s.artifacts = ts, [f"briefs/{f}" for f in files]

    elif name == "ticket-triage-ai":
        db = p / "triage.db"
        pending = _sq(db, "SELECT COUNT(*) FROM tickets WHERE status='pending'")
        p1 = _sq(db, "SELECT COUNT(*) FROM tickets WHERE status='pending' AND priority='P1'")
        if pending is not None:
            s.metric = f"{pending} pending ({p1 or 0} P1)"
            s.artifacts = ["triage.db"]
        s.last_ts = _mtime(db)

    elif name == "voiceline-ai":
        ts, files = _glob_latest(p / "bookings", "*.ics")
        n = len(list((p / "bookings").glob("*.ics"))) if (p / "bookings").exists() else 0
        s.metric = f"{n} bookings created"
        s.last_ts, s.artifacts = ts, [f"bookings/{f}" for f in files]

    elif name == "sql-analyst-agent":
        s.last_ts = _mtime(p / "chart.png", p / "result.csv", p / "retail.duckdb")
        s.metric = "chart + CSV from last query" if (p / "chart.png").exists() else "ready"
        s.artifacts = [a for a in ("chart.png", "result.csv") if (p / a).exists()]

    elif name == "docmind-rag":
        stats = p / ".docmind" / "stats.json"
        if stats.exists():
            data = json.loads(stats.read_text())
            s.metric = f"{data.get('chunks', '?')} chunks / {data.get('sources', '?')} docs indexed"
            s.artifacts = [".docmind/"]
        s.last_ts = _mtime(stats)

    elif name == "mcp-business-server":
        db = p / "bizdesk.db"
        overdue = _sq(db, "SELECT COUNT(*) FROM invoices WHERE status='unpaid' AND due_date < date('now')")
        s.metric = f"{overdue} overdue invoices in demo DB" if overdue is not None else "run seed.py"
        s.last_ts = _mtime(db)
        s.artifacts = ["bizdesk.db"] if db.exists() else []

    elif name == "paper-scout":
        ts, files = _glob_latest(p / "reports", "*.md")
        n = len(list((p / "reports").glob("*.md"))) if (p / "reports").exists() else 0
        s.metric = f"{n} research digests"
        s.last_ts, s.artifacts = ts, [f"reports/{f}" for f in files]

    elif name == "site2bot":
        idx = p / ".site2bot"
        s.metric = "site indexed — widget ready" if idx.exists() else "no site indexed"
        s.last_ts = _mtime(idx / "chroma") or _mtime(idx)
        s.artifacts = [".site2bot/"] if idx.exists() else []

    elif name == "extractor-pipeline":
        csv = p / "results" / "invoices.csv"
        fails = p / "results" / "failures.csv"
        if csv.exists():
            rows = max(0, len(csv.read_text(encoding="utf-8").splitlines()) - 1)
            nf = max(0, len(fails.read_text(encoding="utf-8").splitlines()) - 1) if fails.exists() else 0
            s.metric = f"{rows} extracted · {nf} quarantined"
            s.artifacts = ["results/invoices.csv", "results/invoices.db"]
        s.last_ts = _mtime(csv)

    elif name == "mini-evolve":
        hist = p / "runs" / "history.jsonl"
        if hist.exists():
            lines = [json.loads(l) for l in hist.read_text().splitlines() if l.strip()]
            if lines:
                s.metric = f"fitness {lines[0]['best']:.0f} → {lines[-1]['best']:.0f} over {len(lines)} gens"
            s.artifacts = ["runs/best.py", "runs/fitness.png"]
        s.last_ts = _mtime(hist)

    elif name == "lazy-graphrag-lite":
        idx = p / ".lazygraph"
        s.metric = "corpus indexed (0 LLM calls)" if idx.exists() else "no index"
        s.last_ts = _mtime(idx / "chroma") or _mtime(idx)

    elif name == "compactrag":
        db = p / ".compactrag" / "atoms.db"
        atoms = _sq(db, "SELECT COUNT(*) FROM atoms")
        s.metric = f"{atoms} atomic QA facts" if atoms is not None else "not built"
        s.last_ts = _mtime(db)
        s.artifacts = [".compactrag/atoms.db"] if db.exists() else []

    elif name in ("agent-patterns", "skills-runtime"):
        s.metric = "stateless demos — see test log"
        s.last_ts = _mtime(ROOT / f"_t2_{name}.log")

    return s


PROJECTS: list[tuple[str, str, str]] = [
    ("flowsentry", "business", "n8n ops digests"),
    ("ticket-triage-ai", "business", "support triage queue"),
    ("extractor-pipeline", "business", "documents → validated data"),
    ("site2bot", "business", "website chatbot"),
    ("docmind-rag", "business", "cited doc Q&A"),
    ("voiceline-ai", "business", "voice receptionist"),
    ("salescout-agents", "business", "sales research crew"),
    ("sql-analyst-agent", "business", "NL → SQL analytics"),
    ("mcp-business-server", "business", "MCP over back office"),
    ("paper-scout", "business", "arXiv digests"),
    ("mini-evolve", "paper", "AlphaEvolve loop"),
    ("lazy-graphrag-lite", "paper", "query-time graph RAG"),
    ("skills-runtime", "paper", "Agent Skills runtime"),
    ("agent-patterns", "paper", "Anthropic's 5 patterns"),
    ("compactrag", "paper", "2-call multi-hop RAG"),
]


def _verified_set() -> set[str]:
    done = set()
    for summary in ("TESTS_SUMMARY.txt", "TESTS2_SUMMARY.txt"):
        f = ROOT / summary
        if f.exists():
            for line in f.read_text().splitlines():
                if line.startswith("PASS"):
                    done.add(line.split()[1])
    extra = ROOT / "VERIFIED.txt"   # manual overrides (e.g. verified re-runs)
    if extra.exists():
        done.update(l.strip() for l in extra.read_text().splitlines() if l.strip())
    return done


def scan() -> list[Status]:
    verified = _verified_set()
    out = []
    for name, tier, purpose in PROJECTS:
        st = _probe(name, tier, purpose)
        st.verified = name in verified
        out.append(st)
    return out


if __name__ == "__main__":
    for st in scan():
        v = "✓" if st.verified else " "
        print(f"[{v}] {st.name:22} {st.state:9} {st.last_human:8} {st.metric}")
