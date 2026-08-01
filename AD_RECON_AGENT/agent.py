#!/usr/bin/env python3
"""ADReconAgent — MVP
Phase 1: Autonomous AD reconnaissance agent with LLM analysis and HITL checkpoints.

Usage (Kali, full mode):
    python3 agent.py --target 192.168.56.10 --domain sevenkingdoms.local

Usage (Codespace/fixture mode):
    python3 agent.py --fixture nmap_kingslanding.txt --domain sevenkingdoms.local

Architecture:
    LangGraph state graph (deterministic routing)
    → nmap_node (tool execution)
    → HITL Checkpoint 1 (scope confirmation)
    → llm_analysis_node (LLM reasoning, temp=0.1)
    → HITL Checkpoint 2 (findings review)
    → report_node (structured markdown output)
    → HITL Checkpoint 3 (report approval)

Evaluation target: GOAD lab (192.168.56.0/24)
"""
import subprocess
import json
import pathlib
import sys
import os
import time
import datetime
import argparse
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ──────────────────────────────────────────────────────────
HERE = pathlib.Path(__file__).resolve().parent
AUDIT_DB   = HERE / "audit.db"
TRACE_FILE = HERE / "trace.jsonl"
REPORT_DIR = HERE / "reports"
REPORT_DIR.mkdir(exist_ok=True)
PROMPT_FILE = HERE / "prompts" / "ad_analysis.txt"

# Temperature settings — deliberate per-node design decision
TEMP_CLASSIFY  = 0.1   # classification and control flow nodes
TEMP_REPORT    = 0.7   # report generation prose node

# LLM setup — LiteLLM university sandbox or OpenRouter
llm_classify = ChatOpenAI(
    base_url=os.getenv("LITELLM_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("LITELLM_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
    model=os.getenv("AGENT_MODEL", "Claude Sonnet 4.6"),
    temperature=TEMP_CLASSIFY,
)
llm_report = ChatOpenAI(
    base_url=os.getenv("LITELLM_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key=os.getenv("LITELLM_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
    model=os.getenv("AGENT_MODEL", "Claude Sonnet 4.6"),
    temperature=TEMP_REPORT,
)

# ── State Schema ───────────────────────────────────────────────────────────
class ReconState(TypedDict):
    # Scope
    target:           str
    domain:           str
    confirmed_scope:  bool
    fixture_mode:     bool
    fixture_path:     Optional[str]

    # Tool outputs
    nmap_raw:         str
    open_ports:       list
    services:         dict

    # LLM analysis
    llm_analysis:     str
    findings:         list
    is_dc:            bool
    attack_surface:   str

    # HITL state
    human_reviewed:   bool
    report_approved:  bool

    # Output
    report_content:   str
    report_path:      str

    # Audit
    audit_log:        list
    run_id:           str

# ── Trace / Audit ──────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

def write_trace(event: dict):
    with TRACE_FILE.open("a") as f:
        f.write(json.dumps(event) + "\n")

def audit(state: ReconState, action: str, detail: str = "") -> list:
    entry = {
        "ts":       now_iso(),
        "run_id":   state.get("run_id", "unknown"),
        "action":   action,
        "operator": "colin",
        "detail":   detail,
    }
    write_trace(entry)
    log = list(state.get("audit_log", []))
    log.append(entry)
    return log

# ── System Prompt ──────────────────────────────────────────────────────────
def get_system_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text()
    return """You are an expert Active Directory security auditor conducting
an authorized internal assessment. Analyze the provided enumeration output.
If empty or malformed, reply exactly: INSUFFICIENT DATA
Map all findings to MITRE ATT&CK technique IDs (format: T####.###).
Rate severity as: critical / high / medium / low / info."""

# ── Tool Nodes ─────────────────────────────────────────────────────────────
def scope_intake_node(state: ReconState) -> ReconState:
    """Parse and validate target scope — deterministic."""
    log = audit(state, "scope_intake", f"target={state['target']} domain={state['domain']}")
    print(f"\n[ADReconAgent] Target: {state['target']}")
    print(f"[ADReconAgent] Domain: {state['domain']}")
    print(f"[ADReconAgent] Mode: {'fixture' if state['fixture_mode'] else 'live'}")
    return {**state, "audit_log": log}


def nmap_node(state: ReconState) -> ReconState:
    """Execute nmap or load fixture — tool execution layer."""
    print(f"\n[Step 1/5] Running nmap against {state['target']}...")

    if state["fixture_mode"] and state.get("fixture_path"):
        # Fixture mode — load pre-captured output (Codespace compatible)
        fixture = pathlib.Path(state["fixture_path"])
        if fixture.exists():
            raw = fixture.read_text()
            print(f"  [FIXTURE] Loaded {len(raw)} chars from {fixture.name}")
        else:
            raw = f"ERROR: fixture file not found: {state['fixture_path']}"
    else:
        # Live mode — real nmap execution (requires Kali + network access)
        try:
            t0 = time.monotonic()
            result = subprocess.run(
                ["nmap", "-sV", "-p",
                 "53,88,135,139,389,445,464,636,3268,3269,5985,5986,9389",
                 state["target"]],
                capture_output=True, text=True, timeout=180
            )
            latency = round(time.monotonic() - t0, 2)
            raw = result.stdout
            print(f"  [NMAP] Completed in {latency}s ({len(raw)} chars)")
        except subprocess.TimeoutExpired:
            raw = "TIMEOUT: nmap scan exceeded 180s"
        except FileNotFoundError:
            raw = "ERROR: nmap not found — are you running in Kali?"
        except Exception as e:
            raw = f"ERROR: {str(e)}"

    # Parse open ports from output
    open_ports = []
    for line in raw.splitlines():
        if "/tcp" in line and "open" in line:
            try:
                port = int(line.split("/")[0].strip())
                open_ports.append(port)
            except ValueError:
                pass

    log = audit(state, "nmap_complete",
                f"open_ports={open_ports} chars={len(raw)}")

    return {
        **state,
        "nmap_raw":   raw,
        "open_ports": open_ports,
        "audit_log":  log,
    }


def hitl_checkpoint_1(state: ReconState) -> ReconState:
    """HITL Checkpoint 1 — Scope confirmation before analysis."""
    print("\n" + "="*60)
    print("CHECKPOINT 1 — SCOPE CONFIRMATION")
    print("="*60)
    print(f"Target:      {state['target']}")
    print(f"Domain:      {state['domain']}")
    print(f"Open ports:  {state['open_ports']}")
    print(f"Mode:        {'fixture' if state['fixture_mode'] else 'live nmap'}")
    print(f"\nConfirm scope and proceed to LLM analysis? [y/n]: ", end="", flush=True)

    decision = input().strip().lower()
    approved = decision == "y"

    log = audit(state, "hitl_checkpoint_1",
                f"decision={'approved' if approved else 'rejected'}")

    if not approved:
        print("Scope rejected — halting.")
        sys.exit(0)

    print("Scope confirmed. Proceeding to analysis...")
    return {**state, "confirmed_scope": True, "audit_log": log}


def llm_analysis_node(state: ReconState) -> ReconState:
    """LLM reasoning node — semantic interpretation of tool output.
    Temperature 0.1 — classification and control flow, maximize determinism.
    """
    print("\n[Step 2/5] LLM analyzing nmap output...")
    system = get_system_prompt()
    prompt = f"""{system}

---

Analyze this nmap output from target {state['target']} (domain: {state['domain']}):

{state['nmap_raw']}

Respond with a structured JSON object:
{{
  "is_domain_controller": true/false,
  "confidence": "high/medium/low",
  "host_role": "description of host role",
  "findings": [
    {{
      "title": "finding name",
      "severity": "critical/high/medium/low/info",
      "technique_id": "T####.###",
      "technique_name": "ATT&CK technique name",
      "evidence": "specific evidence from nmap output",
      "next_step": "recommended next enumeration action"
    }}
  ],
  "attack_surface": "2-3 sentence summary of overall attack surface",
  "priority_next_steps": ["ordered list of next tools to run"]
}}"""

    try:
        t0 = time.monotonic()
        response = llm_classify.invoke(prompt)
        latency = round(time.monotonic() - t0, 2)
        raw_response = response.content

        # Parse JSON from response
        content = raw_response.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content.strip())

        findings   = parsed.get("findings", [])
        is_dc      = parsed.get("is_domain_controller", False)
        atk_surface = parsed.get("attack_surface", "")

        print(f"  [LLM] Analysis complete in {latency}s")
        print(f"  [LLM] DC: {is_dc} | Findings: {len(findings)} | "
              f"Confidence: {parsed.get('confidence', 'unknown')}")

    except json.JSONDecodeError:
        # Fallback — treat response as plain text
        raw_response = response.content if 'response' in dir() else "LLM call failed"
        findings = []
        is_dc = False
        atk_surface = raw_response[:500]
        print(f"  [LLM] JSON parse failed — stored raw response")
    except Exception as e:
        raw_response = f"ERROR: {str(e)}"
        findings = []
        is_dc = False
        atk_surface = ""
        print(f"  [LLM] ERROR: {str(e)[:80]}")

    log = audit(state, "llm_analysis_complete",
                f"is_dc={is_dc} findings={len(findings)}")

    return {
        **state,
        "llm_analysis": raw_response,
        "findings":     findings,
        "is_dc":        is_dc,
        "attack_surface": atk_surface,
        "audit_log":    log,
    }


def hitl_checkpoint_2(state: ReconState) -> ReconState:
    """HITL Checkpoint 2 — Enumeration findings review."""
    print("\n" + "="*60)
    print("CHECKPOINT 2 — ENUMERATION REVIEW")
    print("="*60)
    print(f"\nHost role: {'Domain Controller' if state['is_dc'] else 'Member Server / Unknown'}")
    print(f"Findings:  {len(state['findings'])} identified\n")

    for i, f in enumerate(state["findings"], 1):
        print(f"  [{i}] {f.get('title', 'Unknown')} "
              f"[{f.get('severity','?').upper()}] "
              f"{f.get('technique_id','')}")
        print(f"       {f.get('evidence','')[:80]}")

    print(f"\nAttack surface: {state['attack_surface'][:200]}")
    print(f"\nApprove findings and proceed to report? [y/n]: ", end="", flush=True)

    decision = input().strip().lower()
    approved = decision == "y"

    log = audit(state, "hitl_checkpoint_2",
                f"decision={'approved' if approved else 'rejected'} "
                f"findings={len(state['findings'])}")

    if not approved:
        print("Findings rejected — halting. Review nmap output and re-run.")
        sys.exit(0)

    return {**state, "human_reviewed": True, "audit_log": log}


def report_node(state: ReconState) -> ReconState:
    """Generate structured markdown report.
    Temperature 0.7 — prose generation, allow natural variation.
    """
    print("\n[Step 3/5] Generating report...")

    findings_md = ""
    for i, f in enumerate(state["findings"], 1):
        findings_md += f"""
### Finding {i}: {f.get('title', 'Unknown')}

| Field | Value |
|---|---|
| **Severity** | {f.get('severity', 'unknown').upper()} |
| **ATT&CK** | {f.get('technique_id', 'N/A')} — {f.get('technique_name', '')} |
| **Evidence** | {f.get('evidence', 'N/A')} |
| **Next Step** | {f.get('next_step', 'N/A')} |

"""

    report = f"""# ADReconAgent — Engagement Report

**Target:** {state['target']}
**Domain:** {state['domain']}
**Date:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
**Run ID:** {state['run_id']}
**Mode:** {'Fixture (Codespace demo)' if state['fixture_mode'] else 'Live (Kali/GOAD)'}

---

## Host Assessment

**Role:** {'Domain Controller' if state['is_dc'] else 'Member Server / Unknown'}
**Open Ports:** {', '.join(str(p) for p in state['open_ports'])}

## Attack Surface Summary

{state['attack_surface']}

---

## Findings ({len(state['findings'])} total)

{findings_md}

---

## Audit Trail

| Timestamp | Action | Detail |
|---|---|---|
"""
    for entry in state["audit_log"]:
        report += f"| {entry['ts']} | {entry['action']} | {entry.get('detail', '')} |\n"

    report += f"""
---

*Generated by ADReconAgent MVP | Capstone — Agentic AI Systems*
*Operator: colin | Agent: adreconagent-v0.1*
"""

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    report_path = str(REPORT_DIR / f"report_{ts}.md")

    log = audit(state, "report_generated",
                f"path={report_path} chars={len(report)}")

    return {
        **state,
        "report_content": report,
        "report_path":    report_path,
        "audit_log":      log,
    }


def hitl_checkpoint_3(state: ReconState) -> ReconState:
    """HITL Checkpoint 3 — Report approval before output."""
    print("\n" + "="*60)
    print("CHECKPOINT 3 — REPORT APPROVAL")
    print("="*60)
    print(f"\nReport preview (first 500 chars):")
    print("-"*40)
    print(state["report_content"][:500])
    print("-"*40)
    print(f"\nApprove and write report to {state['report_path']}? [y/n]: ",
          end="", flush=True)

    decision = input().strip().lower()
    approved = decision == "y"

    log = audit(state, "hitl_checkpoint_3",
                f"decision={'approved' if approved else 'rejected'}")

    if approved:
        pathlib.Path(state["report_path"]).write_text(state["report_content"])
        print(f"\n✓ Report written: {state['report_path']}")
    else:
        print("\n✗ Report rejected — not written to disk.")

    return {
        **state,
        "report_approved": approved,
        "audit_log":       log,
    }


# ── Conditional routing ────────────────────────────────────────────────────
def route_after_nmap(state: ReconState) -> str:
    """Deterministic routing — LLM never controls this decision."""
    if not state["open_ports"] and "ERROR" not in state["nmap_raw"]:
        return "hitl_checkpoint_1"  # proceed even with no ports (filtered)
    return "hitl_checkpoint_1"


# ── Graph assembly ─────────────────────────────────────────────────────────
def build_graph():
    graph = StateGraph(ReconState)

    graph.add_node("scope_intake",       scope_intake_node)
    graph.add_node("nmap",               nmap_node)
    graph.add_node("hitl_checkpoint_1",  hitl_checkpoint_1)
    graph.add_node("llm_analysis",       llm_analysis_node)
    graph.add_node("hitl_checkpoint_2",  hitl_checkpoint_2)
    graph.add_node("report",             report_node)
    graph.add_node("hitl_checkpoint_3",  hitl_checkpoint_3)

    graph.set_entry_point("scope_intake")
    graph.add_edge("scope_intake",      "nmap")
    graph.add_edge("nmap",              "hitl_checkpoint_1")
    graph.add_edge("hitl_checkpoint_1", "llm_analysis")
    graph.add_edge("llm_analysis",      "hitl_checkpoint_2")
    graph.add_edge("hitl_checkpoint_2", "report")
    graph.add_edge("report",            "hitl_checkpoint_3")
    graph.add_edge("hitl_checkpoint_3", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ADReconAgent MVP")
    parser.add_argument("--target",  default="192.168.56.10",
                        help="Target IP or range")
    parser.add_argument("--domain",  default="sevenkingdoms.local",
                        help="AD domain name")
    parser.add_argument("--fixture", default=None,
                        help="Path to pre-captured nmap output (fixture mode)")
    args = parser.parse_args()

    run_id = datetime.datetime.utcnow().strftime("run_%Y%m%dT%H%M%S")

    # Clear trace for this run
    TRACE_FILE.write_text("")
    write_trace({
        "ts":      now_iso(),
        "step":    "agent_start",
        "run_id":  run_id,
        "target":  args.target,
        "domain":  args.domain,
        "mode":    "fixture" if args.fixture else "live",
    })

    print(f"\n{'='*60}")
    print(f"  ADReconAgent MVP — {run_id}")
    print(f"{'='*60}")

    initial_state: ReconState = {
        "target":          args.target,
        "domain":          args.domain,
        "confirmed_scope": False,
        "fixture_mode":    args.fixture is not None,
        "fixture_path":    args.fixture,
        "nmap_raw":        "",
        "open_ports":      [],
        "services":        {},
        "llm_analysis":    "",
        "findings":        [],
        "is_dc":           False,
        "attack_surface":  "",
        "human_reviewed":  False,
        "report_approved": False,
        "report_content":  "",
        "report_path":     "",
        "audit_log":       [],
        "run_id":          run_id,
    }

    app = build_graph()
    config = {"configurable": {"thread_id": run_id}}

    try:
        final_state = app.invoke(initial_state, config=config)
        write_trace({
            "ts":     now_iso(),
            "step":   "agent_complete",
            "run_id": run_id,
            "findings": len(final_state.get("findings", [])),
            "approved": final_state.get("report_approved", False),
        })
        print(f"\n[ADReconAgent] Complete. Trace: {TRACE_FILE}")
    except KeyboardInterrupt:
        print("\n[ADReconAgent] Interrupted by operator.")
        write_trace({"ts": now_iso(), "step": "agent_interrupted", "run_id": run_id})
    except Exception as e:
        print(f"\n[ADReconAgent] ERROR: {e}")
        write_trace({"ts": now_iso(), "step": "agent_error",
                     "run_id": run_id, "error": str(e)[:200]})
        raise


if __name__ == "__main__":
    main()
