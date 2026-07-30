#!/usr/bin/env python3
"""Build Challenge 5 — Instrumented agent with full observability.

Instruments the quiet_agent.py pipeline with:
  1. Structured JSONL trace logging (timestamp, step, model, tokens, latency, decision)
  2. Human-in-the-loop gate before summary.md is written
  3. Cost/usage reconciliation against common.llm.STATS
  4. Incident-ready: trace is a stranger-readable audit trail

Run from the repo root:
    python3 bc5-observability/quiet_agent.py

Trace output: bc5-observability/trace.jsonl
Summary output: bc5-observability/summary.md

Delegation log:
  Claude Sonnet 4.6 assisted with instrumentation structure.
  HITL gate design, trace schema, and incident diagnosis are Colin's own work.
"""
import json
import pathlib
import sys
import time
import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, STATS

HERE = pathlib.Path(__file__).resolve().parent
import datetime
RUN_ID = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
TRACE_FILE = HERE / f"trace_{RUN_ID}.jsonl"
TOPIC = "why long-running agents need checkpoints"

# ── Trace infrastructure ───────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

def write_trace(event: dict):
    """Append one structured event to the JSONL trace file."""
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")

def traced_chat(step_name: str, messages: list, model=None, **kwargs) -> str:
    """Wrapper around common.llm.chat that emits a trace event per call."""
    prompt_chars = sum(len(m.get("content", "")) for m in messages)
    tokens_before = STATS["tokens"]
    calls_before  = STATS["calls"]
    t0 = time.monotonic()

    try:
        kwargs_to_pass = {k: v for k, v in kwargs.items() if k != "model"}
        if model:
            result = chat(messages, model=model, **kwargs_to_pass)
        else:
            result = chat(messages, **kwargs_to_pass)

        latency   = round(time.monotonic() - t0, 3)
        tokens_used = STATS["tokens"] - tokens_before
        calls_used  = STATS["calls"]  - calls_before

        event = {
            "ts":           now_iso(),
            "step":         step_name,
            "model":        model or "default",
            "prompt_chars": prompt_chars,
            "response_chars": len(result),
            "tokens":       tokens_used,
            "latency_s":    latency,
            "cumulative_tokens": STATS["tokens"],
            "cumulative_calls":  STATS["calls"],
            "cache_hits":   STATS["cache_hits"],
            "decision":     result[:120].replace("\n", " ") + ("..." if len(result) > 120 else ""),
        }
        write_trace(event)

        print(f"  [TRACE] {step_name}: {tokens_used} tokens, {latency}s latency")
        return result
    except Exception as e:
        latency = round(time.monotonic() - t0, 3)
        write_trace({
            "ts":                  now_iso(),
            "step":                step_name,
            "status":              "FAILED",
            "model":               model or "default",
            "error":               str(e)[:200],
            "latency_s":           latency,
            "tokens_before_failure": tokens_before,
            "cumulative_tokens":   STATS["tokens"],
        })
        print(f"  [TRACE] {step_name}: FAILED after {latency}s — {str(e)[:80]}")
        raise


# ── HITL gate ──────────────────────────────────────────────────────────────

def hitl_gate(pending_output: str, cost_summary: dict) -> bool:
    """
    Human-in-the-loop checkpoint before summary.md is written.
    Shows pending output + cost, requires explicit approval.
    Logs the human decision to the trace.
    """
    print("\n" + "="*60)
    print("HUMAN-IN-THE-LOOP CHECKPOINT")
    print("="*60)
    print(f"\nPending output to write to summary.md:\n")
    print("-"*40)
    print(pending_output)
    print("-"*40)
    print(f"\nCost summary so far:")
    print(f"  Total LLM calls : {cost_summary['calls']}")
    print(f"  Total tokens    : {cost_summary['tokens']}")
    print(f"  Cache hits      : {cost_summary['cache_hits']}")
    print(f"  Est. cost       : ~${cost_summary['tokens'] * 0.000003:.5f} (at $3/1M tokens)")
    print(f"\nApprove writing summary.md? [y/n]: ", end="", flush=True)

    decision = input().strip().lower()
    approved = decision == "y"

    # Log the human decision to trace
    write_trace({
        "ts":       now_iso(),
        "step":     "hitl_gate",
        "model":    "human",
        "decision": "approved" if approved else "rejected",
        "cost_at_checkpoint": cost_summary,
        "input":    decision,
    })

    return approved


# ── Cost reconciliation ────────────────────────────────────────────────────

def reconcile_costs():
    """
    Pull usage from common.llm.STATS and attempt to reconcile
    against ~/.openclaw/gateway.log if it exists.
    """
    our_stats = {
        "calls":      STATS["calls"],
        "tokens":     STATS["tokens"],
        "cache_hits": STATS["cache_hits"],
        "est_cost_usd": round(STATS["tokens"] * 0.000003, 6),
    }

    # Attempt gateway log reconciliation
    gateway_log = pathlib.Path.home() / ".openclaw" / "gateway.log"
    gateway_stats = None
    if gateway_log.exists():
        try:
            lines = gateway_log.read_text().splitlines()
            # Parse last N lines for token usage
            total_gateway_tokens = 0
            for line in lines[-50:]:
                try:
                    entry = json.loads(line)
                    total_gateway_tokens += entry.get("total_tokens", 0)
                except Exception:
                    pass
            gateway_stats = {"gateway_tokens_recent": total_gateway_tokens}
        except Exception as e:
            gateway_stats = {"gateway_log_error": str(e)}
    else:
        gateway_stats = {"gateway_log": "not found — using STATS only"}

    reconciliation = {
        "ts":           now_iso(),
        "step":         "cost_reconciliation",
        "our_stats":    our_stats,
        "gateway_stats": gateway_stats,
        "delta_tokens": (
            our_stats["tokens"] - gateway_stats.get("gateway_tokens_recent", our_stats["tokens"])
            if gateway_stats and "gateway_tokens_recent" in gateway_stats
            else "N/A — gateway log unavailable"
        ),
    }
    write_trace(reconciliation)
    return our_stats


# ── Main pipeline ──────────────────────────────────────────────────────────

def main():
    # Clear trace file for this run
    TRACE_FILE.write_text("")
    write_trace({
        "ts":    now_iso(),
        "step":  "pipeline_start",
        "topic": TOPIC,
        "model": "default",
    })

    print(f"\nADReconAgent BC5 — Instrumented Pipeline")
    print(f"Topic: {TOPIC}")
    print(f"Trace: {TRACE_FILE}\n")

    # ── Step 1: Plan ──────────────────────────────────────────────────────
    print("[Step 1/3] Generating research questions...")
    plan = traced_chat(
        step_name="plan",
        messages=[{"role": "user", "content":
            f"List 3 short bullet questions someone should answer to explain: {TOPIC}"}],
        cache=True,
    )

    # ── Step 2: Answer ────────────────────────────────────────────────────
    print("[Step 2/3] Answering questions...")
    answers = traced_chat(
        step_name="answer",
        messages=[{"role": "user", "content":
            "Answer each question in 2 sentences:\n" + plan}],
        model="Claude Sonnet 4.6",
        cache=True,
    )

    # ── Step 3: Summarize ─────────────────────────────────────────────────
    print("[Step 3/3] Generating summary...")
    summary = traced_chat(
        step_name="summarize",
        messages=[{"role": "user", "content":
            "Compress this into a 4-sentence summary for a student:\n" + answers}],
        cache=True,
    )

    # ── Cost reconciliation ───────────────────────────────────────────────
    cost_summary = reconcile_costs()
    print(f"\n[COST] {cost_summary['calls']} calls, "
          f"{cost_summary['tokens']} tokens, "
          f"~${cost_summary['est_cost_usd']:.5f}")

    # ── HITL gate ─────────────────────────────────────────────────────────
    approved = hitl_gate(summary, cost_summary)

    if approved:
        (HERE / "summary.md").write_text(f"# {TOPIC}\n\n{summary}\n")
        write_trace({
            "ts":     now_iso(),
            "step":   "write_output",
            "file":   "bc5-observability/summary.md",
            "chars":  len(summary),
            "status": "written",
        })
        print(f"\n✓ summary.md written ({len(summary)} chars)")
    else:
        write_trace({
            "ts":     now_iso(),
            "step":   "write_output",
            "file":   "bc5-observability/summary.md",
            "status": "rejected by operator",
        })
        print("\n✗ Output rejected — summary.md not written")

    write_trace({
        "ts":     now_iso(),
        "step":   "pipeline_end",
        "status": "approved" if approved else "rejected",
        "final_stats": {
            "calls":   STATS["calls"],
            "tokens":  STATS["tokens"],
            "cache_hits": STATS["cache_hits"],
        },
    })

    print(f"\nFull trace: {TRACE_FILE}")
    print("(trace.jsonl is the stranger-readable audit trail)")


if __name__ == "__main__":
    main()