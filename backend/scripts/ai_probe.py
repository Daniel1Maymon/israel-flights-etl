"""
ai_probe.py — run a prompt suite through the real AI-search pipeline and record what came back.

Purpose: build an evidence base of how the LLM path actually behaves per question shape, so the
failure modes can be handled deliberately instead of discovered by users. It calls
services.ai_search.answer_question directly (the same code the endpoint calls), so the intent, the
handler/fallback routing, the generated SQL and the final prose are all the production ones. It
skips only the endpoint-level guards (rate limit, budget, analytics) because those are about cost
control, not answer quality.

Per prompt it records: the parsed Intent, which path ran (handler | fallback), the fallback SQL if
one was generated, the returned columns/rows, the prose answer, refusal reason, tokens and latency.

Usage:
    ./venv/bin/python scripts/ai_probe.py                     # whole suite
    ./venv/bin/python scripts/ai_probe.py --only neg-01 neg-02
    ./venv/bin/python scripts/ai_probe.py --category negation/absence
    ./venv/bin/python scripts/ai_probe.py --workers 1         # serial (avoid provider rate limits)

Writes scripts/ai_probe_results/<timestamp>.jsonl (one record per prompt) and a .md report.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.services import ai_search as ai_search_mod  # noqa: E402
from app.services.llm_tasks import LLMTasks  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "ai_probe_results"
PROMPTS_FILE = Path(__file__).resolve().parent / "ai_probe_prompts.json"

# Per-thread capture of the two LLM steps that happen inside answer_question. Patching the methods
# is the only way to see the Intent and the fallback SQL: answer_question returns neither, and the
# point of this harness is to know WHY an answer was wrong, not just that it was.
_local = threading.local()

_orig_interpret = LLMTasks.interpret
_orig_generate_sql = LLMTasks.generate_sql


def _interpret(self, question: str):
    intent, tokens = _orig_interpret(self, question)
    getattr(_local, "capture", {})["intent"] = intent.model_dump()
    return intent, tokens


def _generate_sql(self, question: str):
    sql, tokens = _orig_generate_sql(self, question)
    getattr(_local, "capture", {})["fallback_sql"] = sql
    return sql, tokens


LLMTasks.interpret = _interpret
LLMTasks.generate_sql = _generate_sql


def run_one(case: dict) -> dict:
    _local.capture = {}
    started = time.perf_counter()
    record: dict = {
        "id": case["id"],
        "run": case.get("run", 1),
        "category": case["category"],
        "lang": case.get("lang"),
        "prompt": case["prompt"],
        "note": case.get("note"),
    }
    try:
        response, tokens = ai_search_mod.answer_question(case["prompt"])
        record.update(
            {
                "ok": True,
                "intent": _local.capture.get("intent"),
                "fallback_sql": _local.capture.get("fallback_sql"),
                "source": response.source,
                "refused": response.refused,
                "reason": response.reason,
                "answer": response.answer,
                "columns": response.columns,
                "row_count": len(response.rows),
                "rows": response.rows[:10],  # first 10 is enough to judge the answer
                "data_start": response.data_start,
                "data_end": response.data_end,
                "tokens": tokens,
            }
        )
    except Exception as e:  # a crash IS a finding — record it, keep the suite going
        record.update(
            {
                "ok": False,
                "intent": _local.capture.get("intent"),
                "fallback_sql": _local.capture.get("fallback_sql"),
                "exception": f"{type(e).__name__}: {e}",
            }
        )
    record["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return record


def _fmt_rows(rows: list[dict], limit: int = 3) -> str:
    if not rows:
        return "_(no rows)_"
    return "\n".join(
        "`" + json.dumps(r, ensure_ascii=False, default=str) + "`" for r in rows[:limit]
    )


def _signature(r: dict) -> str:
    """What a run resolved to — used to spot the same prompt resolving two different ways."""
    intent = (r.get("intent") or {})
    if not r.get("ok"):
        return "exception"
    if r.get("refused"):
        return f"refused:{r.get('reason')}"
    return f"{intent.get('intent')}/{r.get('source')}"


def write_report(records: list[dict], path: Path) -> None:
    lines = [
        f"# AI search probe — {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        f"{len(records)} runs through `answer_question` (endpoint guards bypassed).",
        "",
    ]

    # Instability first: a prompt that resolves two ways across identical runs is a defect on its
    # own, independent of whether any single answer looks right.
    by_id: dict[str, list[dict]] = {}
    for r in records:
        by_id.setdefault(r["id"], []).append(r)
    unstable = {k: v for k, v in by_id.items() if len({_signature(r) for r in v}) > 1}
    if unstable:
        lines += ["## ⚠️ Unstable prompts (same input, different resolution)", ""]
        for pid, runs in unstable.items():
            sigs = ", ".join(f"run {r['run']}: {_signature(r)}" for r in runs)
            lines.append(f"- **{pid}** — {runs[0]['prompt']} → {sigs}")
        lines.append("")

    lines += [
        "| id | run | category | prompt | intent | path | rows | outcome |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in records:
        intent = (r.get("intent") or {}).get("intent") if r.get("intent") else None
        valid = (r.get("intent") or {}).get("valid") if r.get("intent") else None
        intent_cell = f"{intent}{'' if valid in (None, True) else ' (invalid)'}"
        if not r.get("ok"):
            outcome = "💥 exception"
        elif r.get("refused"):
            outcome = f"refused: {r.get('reason')}"
        else:
            outcome = "answered"
        prompt = r["prompt"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} | {r['run']} | {r['category']} | {prompt} | {intent_cell} | "
            f"{r.get('source') or '-'} | {r.get('row_count', 0)} | {outcome} |"
        )

    lines += ["", "---", "", "## Full records", ""]
    for r in records:
        lines += [
            f"### {r['id']} (run {r['run']}) — {r['category']}",
            "",
            f"**Prompt:** {r['prompt']}",
        ]
        if r.get("note"):
            lines.append(f"**Note:** {r['note']}")
        lines += [
            "",
            f"**Intent:** `{json.dumps(r.get('intent'), ensure_ascii=False)}`",
            "",
        ]
        if r.get("fallback_sql"):
            lines += ["**Fallback SQL:**", "", "```sql", r["fallback_sql"], "```", ""]
        if not r.get("ok"):
            lines += [f"**Exception:** `{r.get('exception')}`", ""]
        else:
            lines += [
                f"**Path:** {r.get('source') or '-'} · **Refused:** {r.get('refused')}"
                f"{' (' + str(r.get('reason')) + ')' if r.get('reason') else ''}"
                f" · **Rows:** {r.get('row_count')} · **Tokens:** {r.get('tokens')}"
                f" · **Latency:** {r.get('latency_ms')}ms",
                "",
                f"**Answer:** {r.get('answer') or '_(none)_'}",
                "",
                f"**Columns:** {r.get('columns')}",
                "",
                "**Rows (first 3):**",
                "",
                _fmt_rows(r.get("rows") or []),
                "",
            ]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="run only these prompt ids")
    ap.add_argument("--category", nargs="*", help="run only these categories")
    ap.add_argument("--workers", type=int, default=3, help="parallel prompts (default 3)")
    ap.add_argument("--repeat", type=int, default=1, help="runs per prompt (catches unstable intents)")
    ap.add_argument("--tag", default="", help="suffix for the output filenames")
    args = ap.parse_args()

    cases = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]
    if args.category:
        cases = [c for c in cases if c["category"] in set(args.category)]
    if not cases:
        sys.exit("no prompts selected")

    # interpret() runs at temperature 0, yet the same prompt has been seen resolving to different
    # intents — so one run per prompt cannot tell a stable behaviour from a coin flip.
    order = [c["id"] for c in cases]
    cases = [dict(c, run=n + 1) for c in cases for n in range(max(1, args.repeat))]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.tag}" if args.tag else "")

    print(f"running {len(cases)} prompts with {args.workers} worker(s)...", flush=True)
    done = 0
    lock = threading.Lock()

    def run_and_log(case: dict) -> dict:
        nonlocal done
        rec = run_one(case)
        with lock:
            done += 1
            status = (
                "EXC" if not rec.get("ok")
                else f"refused:{rec.get('reason')}" if rec.get("refused")
                else f"{rec.get('source')}/{rec.get('row_count')} rows"
            )
            print(f"  [{done}/{len(cases)}] {rec['id']:<12} r{rec['run']} {status}", flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        records = list(pool.map(run_and_log, cases))

    records.sort(key=lambda r: (order.index(r["id"]), r["run"]))

    jsonl = RESULTS_DIR / f"{stamp}.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    md = RESULTS_DIR / f"{stamp}.md"
    write_report(records, md)

    total_tokens = sum(r.get("tokens") or 0 for r in records)
    print(f"\n{jsonl}\n{md}\ntotal tokens: {total_tokens}")


if __name__ == "__main__":
    main()
