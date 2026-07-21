# BC3 Write-Up — Reliability & Rollback

**Repo:** this repo · **Live evidence:** `bc3-recovery.cast` (asciinema, committed)

---

## Flaw Diagnosis

Six reliability flaws were identified in `broken_agent.py`:

| # | Location | Flaw | Bad day that triggers it |
|---|---|---|---|
| 1 | `urlopen(req)` | No timeout, no retry | Network blip → hangs forever |
| 2 | `json.loads(out)` | Raw model output parsed with no validation or fence-stripping | Model wraps reply in prose or ```json fence → `json.loads` raises, swallowed silently |
| 3 | `REPORT.write_text("# Approved Changes\n\n")` at top of `main()` | Destroys live report before any work is done | Crash or kill mid-run → report is blank or gone |
| 4 | `for item in items:` with no checkpoint | No progress persisted to disk | Codespace stop/restart → full reprocessing, double token spend |
| 5 | `except Exception: pass` | Silent failure — exceptions disappear | Any per-item error → item silently skipped, not counted |
| 6 | `print(f"✅ Done! {approved}…")` always executes | Partial failure reported as full success | Half the queue fails → exit 0, operator misled |

---

## Fixes in `fixed_agent.py`

1. **Timeout + retries** — delegated entirely to `common.llm.chat(timeout=120, retries=2)` which already implements exponential backoff. No reinvention.
2. **JSON validation** — `strip_json()` removes markdown fences via regex, finds the first `{...}` block, then validates that `risk` ∈ `{low, medium, high}` and `reason` is a non-empty string. Bad replies raise `ValueError`, caught per-item.
3. **Staged report write** — all results collected first; written to `approved_report.md.tmp`, then `Path.replace()` atomically renames it over the live report. A crash before the rename leaves the previous report intact.
4. **Checkpoint** — after every item, `checkpoint.json` is written atomically (temp + rename). On startup, already-processed IDs are skipped. Re-running after success is fully idempotent — zero tokens re-spent.
5. **Explicit failure tracking** — `failed[]` list collects every per-item exception with its message. Failures appear in the report under "## Failed Items".
6. **Honest exit** — final banner shows `approved=N failed=N skipped=N`; exits with code 1 if any item failed.

---

## Recovery Demonstrations

Both captured in `bc3-recovery.cast` (commit `bc3-recovery.cast`).

### Demo 1 — Mid-run kill → resume
- Agent started with `--slow` flag (2s pause between items for killable window).
- `SIGTERM` sent after 4 items processed (CR-101 through CR-104 checkpointed).
- `checkpoint.json` inspected — confirmed 4 entries persisted.
- Agent re-run: skipped CR-101–104, processed CR-105–108, report complete.
- **Result:** no items re-processed, no tokens re-spent, approved_report.md valid.

### Demo 2 — Injected failure
- `BAD_ITEMS=CR-103,CR-105` env var forces those items to raise `RuntimeError`.
- Agent ran to completion: 3 approved, 2 failed, 0 silent.
- Report contains "## Failed Items" section listing CR-103 and CR-105 with error messages.
- Exit code 1; approved items (CR-102, CR-104, CR-108) unaffected.

### Idempotency
- Re-running after full success: all 8 items skipped from checkpoint, exit 0.

---

## Delegation Log

**AI used:** Claw — Claude Sonnet 4.6 via OU LiteLLM Sandbox (OpenClaw familiar)

**Key prompts that worked:**
- *"Diagnose all flaws in broken_agent.py — map each to the bad day that triggers it"* — produced the complete 6-flaw table above without missing any.
- *"Build fixed_agent.py: use common.llm.chat for retries/timeout, strip_json for validation, staged .tmp write for rollback, checkpoint.json atomic write, honest failure counts and exit code"* — generated the full agent in one pass, matching spec.

**What it got wrong / what I fixed:**
- First version of `fixed_agent.py` did not include the `--slow` flag needed to create a killable mid-run window for the demo. Added `--slow` as a second pass.
- The asciinema demo initially only showed idempotent resume (checkpoint already full), not a true mid-run kill. Corrected by clearing checkpoint, running with `--slow`, killing at 8s, then resuming — producing genuine partial-then-resume evidence.

**How I verified the result:**
1. Read every line of `fixed_agent.py` and mapped each fix back to the flaw table.
2. Ran clean → confirmed 3 approved, exit 0.
3. Ran again → confirmed all 8 skipped, zero tokens re-spent (cache hits), exit 0.
4. Ran with `BAD_ITEMS=CR-103,CR-105` → confirmed exit 1, failures in report, approved unchanged.
5. Ran mid-run kill scenario → confirmed checkpoint contained exactly the 4 items processed before kill, resume picked up at item 5.
6. Inspected `approved_report.md` after each run — contents matched expected classifications.
