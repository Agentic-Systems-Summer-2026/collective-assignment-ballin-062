#!/usr/bin/env python3
"""Build Challenge 4 starter — evaluation harness.

Run the full local sweep from the repo root:
    python3 bc4-evals/harness.py            # all cases, cached
CI runs the pytest wrapper (test_eval.py) on every push: a small live sweep
capped by EVAL_LIVE_N (default 5).

The harness evaluates TARGET below. It defaults to a plain model call — point
it at YOUR system (bc1 agent, capstone slice) by replacing `target()`.

Three layers, per the pre-read:
  1. assertions  — cheap, deterministic checks (see check_case)
  2. LLM-as-judge — calibrate against your own labels before trusting it
  3. error analysis — look at the failures, not just the score
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common.llm import chat, STATS

HERE = pathlib.Path(__file__).resolve().parent
CASES = HERE / "cases.jsonl"
PROMPT_FILE = pathlib.Path(__file__).resolve().parents[1] / "prompts" / "ad_analysis.txt"

PASS_THRESHOLD = 0.80   # CI gate fails below this — tuned from calibration run
JUDGE_MODEL = "Claude Sonnet 4.6"   # Sonnet-class required for judge layer


def _system_prompt() -> str:
    if PROMPT_FILE.exists():
        return PROMPT_FILE.read_text()
    return (
        "You are an expert AD security tester and auditor. Analyze the provided "
        "enumeration output. If empty or malformed, reply: INSUFFICIENT DATA"
    )


def target(prompt: str) -> str:
    """The system under test: ADReconAgent LLM analysis node.

    Takes raw tool output (nmap / ldapsearch / NetExec) as the user message
    and returns structured AD analysis. This is the portable, Codespace-safe
    slice of the full agent — no subprocess or network access needed.
    """
    system = _system_prompt()
    content = f"{system}\n\n---\n\n{prompt}" if prompt.strip() else system
    return chat(
        [
            {
                "role": "user",
                "content": content,
            }
        ],
        model=JUDGE_MODEL,
        max_tokens=600,
        temperature=0,   # deterministic for eval
        cache=True,
    )


def check_case(case: dict, output: str) -> tuple[bool, str]:
    """Layer 1: assertions. Deterministic, explainable, fast."""
    out = output.lower()
    for s in case.get("must_contain", []):
        if s.lower() not in out:
            return False, f"missing required substring: {s!r}"
    for s in case.get("must_not_contain", []):
        if s.lower() in out:
            return False, f"contains forbidden substring: {s!r}"
    if "max_chars" in case and len(output) > case["max_chars"]:
        return False, f"too long: {len(output)} > {case['max_chars']}"
    return True, "ok"


def judge_case(case: dict, output: str) -> tuple[bool, str]:
    """Layer 2: LLM-as-judge. Sonnet-class model required.

    Calibrated against 10 hand-labeled outputs — see Build Journal for
    agreement numbers. Only applied when judge_criteria is present.
    """
    if "judge_criteria" not in case:
        return True, "no judge criteria"
    verdict = chat(
        [
            {
                "role": "user",
                "content": (
                    f"You are a strict security assessment grader.\n"
                    f"Criteria: {case['judge_criteria']}\n\n"
                    f"CANDIDATE ANSWER:\n{output}\n\n"
                    'Reply ONLY with JSON {"pass": true|false, "reason": "<one line>"}'
                ),
            }
        ],
        model=JUDGE_MODEL,
        max_tokens=450,
        temperature=0,
        cache=True,
    )
    try:
        j = json.loads(verdict[verdict.find("{") : verdict.rfind("}") + 1])
        return bool(j.get("pass")), j.get("reason", "")
    except Exception:
        return False, "judge reply unparseable: " + verdict[:80]


def run_sweep(limit=None):
    cases = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    if limit:
        cases = cases[:limit]
    results = []
    for c in cases:
        out = target(c["prompt"])
        ok_a, why_a = check_case(c, out)
        ok_j, why_j = (
            judge_case(c, out) if ok_a else (False, "skipped (assertion failed)")
        )
        results.append(
            {
                "id": c["id"],
                "pass": ok_a and ok_j,
                "assertion": why_a,
                "judge": why_j,
                "output": out,
            }
        )
    return results


def main():
    results = run_sweep()
    rate = sum(r["pass"] for r in results) / len(results)
    print(f"{'ID':20} {'PASS':5} notes")
    for r in results:
        note = r["assertion"] if r["assertion"] != "ok" else r["judge"]
        print(f"{r['id']:20} {str(r['pass']):5} {note}")
    print(
        f"\npass rate: {rate:.0%}  (threshold {PASS_THRESHOLD:.0%})"
        f"   STATS: {STATS}"
    )
    # Layer 3: open last_run.json and do your error analysis there
    (HERE / "last_run.json").write_text(json.dumps(results, indent=2))
    print("full outputs -> bc4-evals/last_run.json (do your error analysis there)")
    if rate < PASS_THRESHOLD:
        sys.exit(1)


if __name__ == "__main__":
    main()