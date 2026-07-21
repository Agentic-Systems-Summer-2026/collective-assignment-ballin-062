# Build Journal

One short entry per build — all five Build Challenges plus the smaller daily
builds. Four to eight sentences each: this is a lab notebook, not an essay.
It is also your AI-use disclosure record for the course. Graded on
completeness and honesty about failures, not polish. (50 pts, due Aug 6.)

Template per entry:

## Day N — <build name>
- **What I built:**
- **What failed:**
- **What I changed:**
- **Where AI helped, and how I verified its output:**

---

## Day 3 — BC3: Reliability & Rollback
- **What I built:** `fixed_agent.py` — a hardened version of the broken change-request classifier. Added disk checkpointing (`checkpoint.json`, atomic write via `.tmp` rename), staged report output (writes to `.tmp` then renames, never destroys live report mid-run), honest failure accounting (failed items logged and reported, exit code 1 on any failure), and JSON validation with fence-stripping via `strip_json()`. Retries and timeouts delegated to `common.llm.chat()`. Prompt extracted to `prompts/bc3-classify.txt`.
- **What failed:** First attempted to write the report inline while processing — realized that mirrors the original flaw. Restructured to collect all results first, then do a single staged write at the end.
- **What I changed:** Introduced `REPORT_TMP` staging path and `pathlib.Path.replace()` for atomic rename; added `BAD_ITEMS` env var for injected failure demo without touching live code paths.
- **Where AI helped, and how I verified its output:** Claw (Claude Sonnet 4.6) wrote `fixed_agent.py` and `bc3-classify.txt`. Verified by: (1) clean run — 8 items classified, 3 approved, exit 0; (2) re-run — all 8 skipped from checkpoint, zero tokens spent, exit 0 (idempotent); (3) injected failure (`BAD_ITEMS=CR-103,CR-105`) — 2 failures surfaced in report, exit 1, approved items unaffected. Asciinema recording committed as `bc3-recovery.cast`.

---

## Day 1 — Lab 0 (example format; replace with your own)
- **What I built:** connected my Codespace to OpenRouter and ran the end-to-end demo.
- **What failed:** first run rejected my key — I had pasted it with a trailing space.
- **What I changed:** re-ran `bash scripts/set-key.sh` and re-ran the gateway task.
- **Where AI helped, and how I verified its output:** asked the TUI to explain the agent loop; cross-checked its claims against the gateway log lines.
