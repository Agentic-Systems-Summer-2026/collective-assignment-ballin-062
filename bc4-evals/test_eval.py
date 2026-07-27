"""CI regression gate (runs on every push via .github/workflows/eval.yml).

Small LIVE sweep against the course endpoint (OU LiteLLM Sandbox if
LITELLM_API_KEY is set, else OpenRouter via OPENROUTER_API_KEY): first
EVAL_LIVE_N cases (default 5), temperature 0, response caching on.

Keep it capped — a push should cost pennies. The gate fails the build when
the pass rate drops below harness.PASS_THRESHOLD. Thresholds only move UP,
with evidence.

Key hygiene: keys live ONLY in repository secrets. Never commit them.
"""
import os
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Accept either OU LiteLLM or OpenRouter key
_has_litellm = bool(os.environ.get("LITELLM_API_KEY"))
_has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

if not _has_litellm and not _has_openrouter:
    pytest.skip(
        "No endpoint secret set (LITELLM_API_KEY or OPENROUTER_API_KEY) — "
        "eval gate needs a repository secret (Settings → Secrets → Actions).",
        allow_module_level=True,
    )

import harness  # noqa: E402

LIVE_N = int(os.environ.get("EVAL_LIVE_N", "5"))


def test_regression_gate():
    """CI gate: sweep first LIVE_N cases and assert pass rate >= threshold."""
    results = harness.run_sweep(limit=LIVE_N)
    rate = sum(r["pass"] for r in results) / len(results)
    failing = [
        f"{r['id']}: assertion={r['assertion']} | judge={r['judge']}"
        for r in results
        if not r["pass"]
    ]
    assert rate >= harness.PASS_THRESHOLD, (
        f"ADReconAgent eval REGRESSION: pass rate {rate:.0%} < "
        f"threshold {harness.PASS_THRESHOLD:.0%}\n"
        + "\n".join(failing)
    )