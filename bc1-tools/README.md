# Build Challenge 1 — Tool/Function Calling (50 pts, due Wed Jul 15, 11:59 PM CT)

**Objective.** Write 2–3 custom tools for your agent and trace a tool call
end-to-end (request → tool schema → call → result → final answer). Design at
least one tool interface to return **token-efficient** results, and show the
before/after.

**Starter state.** `agent.py` runs now: a JSON tool-loop over the sample notes
in `data/`, printing a full trace each step. One tool
(`search_notes_verbose`) is deliberately wasteful.

**Acceptance check.**
- `python3 bc1-tools/agent.py "<your task>"` completes using at least one of
  YOUR tools, chosen by the model (not hard-coded).
- Your write-up includes one full trace and a before/after comparison of the
  wasteful vs. token-efficient tool (use `STATS` — calls, tokens).
- System prompt changes are in `prompts/` with `PROMPTS.md` entries.

**Rubric (50 pts).** Tools work & are model-discoverable from the spec (20) ·
token-efficiency redesign with measured before/after (15) · end-to-end trace
and write-up quality (10) · Build Journal entry (5).

Pairing is encouraged; write-ups are individual. Disclose and verify any AI
assistance.
