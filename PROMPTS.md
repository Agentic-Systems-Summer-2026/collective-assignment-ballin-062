# Prompt Changelog

Prompts are software artifacts. Every prompt lives as a file in `prompts/` —
never inline-only — and **every change gets a line here**: what changed, why,
and the observed effect. BC2's write-up must cite at least two entries.

Format: `YYYY-MM-DD · file · what changed · why · observed effect`

| Date | Prompt file | What changed | Why | Observed effect |
|---|---|---|---|---|
| 2026-07-13 | bc1-agent-system.txt | (seed) initial system prompt from template | starting point | agent answers but tool JSON occasionally wrapped in prose |
| 2026-07-21 | bc3-classify.txt | (seed) initial classification prompt for BC3 fixed_agent | strict JSON-only reply instruction to prevent fence/prose wrapping | model returns clean JSON; strip_json() fence-strip still retained as defense-in-depth |
