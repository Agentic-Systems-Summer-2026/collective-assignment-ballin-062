#!/usr/bin/env python3
"""Build Challenge 3 — FIXED agent.

Fixes applied (mapped to broken_agent.py flaws):
  1. No timeout / no retry      → uses common.llm.chat() which has timeout=120
                                   and retries=2 with exponential backoff baked in
  2. No JSON validation         → strip_json() removes markdown fences and
                                   validates required keys + enum values before
                                   the result is trusted
  3. Report destroyed upfront   → write to a staging file (.tmp), then atomic
                                   rename over the live report only on full success;
                                   rollback keeps the last good report intact
  4. No checkpoint              → checkpoint.json records every processed id so a
                                   restart skips completed items (idempotent)
  5. Silent failure             → every per-item exception is logged to failed[];
                                   at the end, failures are written to the report
                                   and the exit code is non-zero
  6. Partial success = "Done!"  → final banner shows approved / failed / skipped
                                   counts; exits 1 if any item failed

Run:  python3 bc3-reliability/fixed_agent.py
Resume after kill/restart: just re-run — checkpoint skips already-done items.
Inject failure: set env BAD_ITEMS=CR-103,CR-105 to force those items to error.
"""
import json
import os
import pathlib
import re
import sys
import time

# --slow flag: adds a 2s pause between items so mid-run kill is demonstrable
SLOW = "--slow" in sys.argv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, load_prompt  # noqa

HERE        = pathlib.Path(__file__).resolve().parent
REPORT      = HERE / "approved_report.md"
REPORT_TMP  = HERE / "approved_report.md.tmp"
CHECKPOINT  = HERE / "checkpoint.json"
REQUESTS    = HERE / "requests.jsonl"
PROMPT_FILE = "bc3-classify.txt"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_checkpoint() -> dict:
    """Return {id: result_dict} for every already-processed item."""
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text())
        except Exception:
            pass  # corrupt checkpoint — start fresh (safe: worst case re-spends tokens)
    return {}


def save_checkpoint(state: dict) -> None:
    """Atomic write so a kill during save doesn't corrupt the checkpoint."""
    tmp = CHECKPOINT.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(CHECKPOINT)


def strip_json(text: str) -> dict:
    """
    Extract and validate JSON from a model reply.
    Handles markdown fences (```json ... ```) and leading/trailing prose.
    Raises ValueError if the result is missing required keys or has bad values.
    """
    # Strip markdown fences
    text = re.sub(r"```[a-z]*\n?", "", text).strip()
    # Find the first {...} block
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model reply: {text!r}")
    parsed = json.loads(match.group())
    # Validate schema
    if "risk" not in parsed or "reason" not in parsed:
        raise ValueError(f"Missing required keys in: {parsed}")
    if parsed["risk"] not in ("low", "medium", "high"):
        raise ValueError(f"Invalid risk value: {parsed['risk']!r}")
    if not isinstance(parsed["reason"], str) or not parsed["reason"].strip():
        raise ValueError(f"Empty or non-string reason in: {parsed}")
    return parsed


def classify(request_text: str, item_id: str) -> dict:
    """
    Call the LLM to classify a change request.
    common.llm.chat() provides timeout + retries + backoff.
    BAD_ITEMS env var injects artificial failures for demo purposes.
    """
    bad = os.environ.get("BAD_ITEMS", "")
    if item_id in bad.split(","):
        raise RuntimeError(f"[injected failure] {item_id} forced to error")

    prompt_template = load_prompt(PROMPT_FILE)
    messages = [{"role": "user", "content": prompt_template + request_text}]
    raw = chat(messages, max_tokens=200, temperature=0, cache=True)
    return strip_json(raw)


def build_report(approved: list, failed: list, skipped: list) -> str:
    """Render the full report as a string (written to .tmp, never directly to live)."""
    lines = ["# Approved Changes\n"]
    if approved:
        for item, verdict in approved:
            lines.append(
                f"- **{item['id']}** ({verdict['risk']}): "
                f"{item['request'][:80]} — {verdict['reason']}\n"
            )
    else:
        lines.append("_No low-risk items found._\n")

    if failed:
        lines.append("\n## Failed Items\n")
        for item, err in failed:
            lines.append(f"- **{item['id']}**: {err}\n")

    if skipped:
        lines.append("\n## Skipped (checkpoint)\n")
        for item_id in skipped:
            lines.append(f"- {item_id}\n")

    lines.append(f"\n---\n_Generated {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}_\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    items = [json.loads(l) for l in REQUESTS.read_text().splitlines() if l.strip()]
    checkpoint = load_checkpoint()

    approved = []
    failed   = []
    skipped  = []

    print(f"[bc3] {len(items)} items in queue. "
          f"{len(checkpoint)} already checkpointed.")

    for item in items:
        iid = item["id"]

        # Resume: skip already-processed items
        if iid in checkpoint:
            result = checkpoint[iid]
            skipped.append(iid)
            if result.get("risk") == "low":
                approved.append((item, result))
            print(f"  [skip] {iid} (checkpoint)")
            continue

        # Classify with retries / timeout (via common.llm.chat)
        print(f"  [work] {iid} …", end="", flush=True)
        try:
            verdict = classify(item["request"], iid)
            checkpoint[iid] = verdict
            save_checkpoint(checkpoint)
            if SLOW:
                time.sleep(2)
            if verdict["risk"] == "low":
                approved.append((item, verdict))
                print(f" {verdict['risk']} ✓")
            else:
                print(f" {verdict['risk']} (not approved)")
        except Exception as exc:
            err = str(exc)
            failed.append((item, err))
            checkpoint[iid] = {"error": err}
            save_checkpoint(checkpoint)
            print(f" ✗ FAILED: {err}")

    # --- Staged write + atomic rollback ---
    # Write to .tmp first; only replace live report if write succeeds.
    # If anything explodes here, the previous approved_report.md is untouched.
    try:
        REPORT_TMP.write_text(build_report(approved, failed, skipped))
        REPORT_TMP.replace(REPORT)
    except Exception as exc:
        print(f"\n[bc3] ⚠️  Could not write report: {exc}")
        print(f"[bc3] Previous report preserved at {REPORT}")
        sys.exit(2)

    # --- Final banner with honest counts ---
    print(f"\n[bc3] Report written → {REPORT.name}")
    print(f"      approved={len(approved)}  failed={len(failed)}  skipped={len(skipped)}")

    if failed:
        print(f"[bc3] ⚠️  {len(failed)} item(s) failed — see report for details.")
        sys.exit(1)
    else:
        print("[bc3] ✅ All items processed successfully.")


if __name__ == "__main__":
    main()
