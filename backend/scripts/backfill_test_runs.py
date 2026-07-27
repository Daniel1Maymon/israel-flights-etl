"""
backfill_test_runs.py — import probe runs that predate ai_test_runs (or that failed to log).

The harness only started writing to ai_test_runs after the table existed; the runs from
2026-07-25 spent 181,111 tokens that nothing recorded. Every jsonl in ai_probe_results/ carries a
`tokens` field per record, so the rollup can be reconstructed exactly rather than estimated.

    ./venv/bin/python scripts/backfill_test_runs.py            # import anything not yet recorded
    ./venv/bin/python scripts/backfill_test_runs.py --dry-run  # show what would be imported

Idempotent by `artifact` (the jsonl filename): a file already in the table is skipped, so running
this twice cannot double-count. Timestamps come from the filename, so imported rows land in the
month the run actually happened.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.services.probe_runs import ensure_test_runs_table  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "ai_probe_results"


def summarise(path: Path) -> dict:
    """Rebuild one run's rollup from its jsonl: distinct prompts, repeats, total tokens."""
    tokens = 0
    ids: set[str] = set()
    runs: set[int] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Field names differ between harnesses (ai_probe writes `tokens`/`id`/`run`; other
        # harnesses have used total_tokens/token_count and prompt_id/case_id). Accept any of
        # them rather than silently importing a run as zero tokens -- an under-count here is
        # worse than no row at all, because it looks like an answer.
        tokens += (
            rec.get("tokens")
            or rec.get("total_tokens")
            or rec.get("token_count")
            or 0
        )
        ident = rec.get("id") or rec.get("prompt_id") or rec.get("case_id") or rec.get("prompt")
        if ident:
            ids.add(str(ident))
        run_no = rec.get("run") or rec.get("run_no") or rec.get("iteration")
        if run_no:
            runs.add(int(run_no))

    # filenames are <YYYYmmdd-HHMMSS>[-tag].jsonl
    parts = path.stem.split("-")
    stamp = "-".join(parts[:2])
    tag = "-".join(parts[2:])
    try:
        created = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
    except ValueError:
        created = None

    return {
        "artifact": path.name,
        "tag": tag or None,
        "questions": len(ids),
        "repeats": max(runs) if runs else 1,
        "tokens": tokens,
        "created_at": created,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show what would be imported, write nothing")
    ap.add_argument(
        "--dir",
        action="append",
        default=None,
        help="extra directory of run jsonl to import (repeatable). Other harnesses write "
             "elsewhere -- e.g. a session scratchpad -- and their spend counts too.",
    )
    args = ap.parse_args()

    dirs = [RESULTS_DIR] + [Path(d).expanduser() for d in (args.dir or [])]
    files: list[Path] = []
    for d in dirs:
        if not d.is_dir():
            print(f"  warn   {d} is not a directory, skipping")
            continue
        files.extend(sorted(d.glob("*.jsonl")))
    if not files:
        sys.exit(f"no jsonl files found in: {', '.join(str(d) for d in dirs)}")

    db = SessionLocal()
    try:
        ensure_test_runs_table(db.get_bind())
        existing = {
            r[0]
            for r in db.execute(text("SELECT artifact FROM ai_test_runs WHERE artifact IS NOT NULL"))
        }

        imported = skipped = total = 0
        for path in files:
            row = summarise(path)
            if row["artifact"] in existing:
                print(f"  skip   {row['artifact']} (already recorded)")
                skipped += 1
                continue

            print(
                f"  import {row['artifact']}: {row['questions']} prompts "
                f"x{row['repeats']} = {row['tokens']:,} tokens"
            )
            total += row["tokens"]
            imported += 1
            if args.dry_run:
                continue

            db.execute(
                text("""
                    INSERT INTO ai_test_runs
                        (created_at, tag, questions, repeats, tokens, artifact)
                    VALUES
                        (COALESCE(:created_at, now()), :tag, :questions, :repeats, :tokens, :artifact)
                """),
                row,
            )
        if not args.dry_run:
            db.commit()

        verb = "would import" if args.dry_run else "imported"
        print(f"\n{verb} {imported} run(s), {total:,} tokens; skipped {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
