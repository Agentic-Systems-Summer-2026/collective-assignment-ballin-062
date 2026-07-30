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

## Day 2 — Mini-Build: Workflow vs. Agent

| Run | Version  | Calls | Tokens | Turns | Score /7 | Notes |
|-----|----------|-------|--------|-------|----------|-------|
| 1   | workflow |   3   |  830   | n/a   |     7    |       |
| 2   | workflow |   3   |  811   | n/a   |     7    |       |
| 3   | workflow |   3   |  820   | n/a   |     7    |       |
| 4   | agent    |   4   |  2543  |  4    |     7    |       |
| 5   | agent    |   4   |  2590  |  4    |     7    |       |
| 6   | agent    |   4   |  2611  |  4    |     7    |       |

Verdict — for THIS task I would ship the (workflow / agent) because: 
Workflow. The number of tokens used is roughly 1/3 the cost of the agent without sacrificing performance. However, I would run more than 3 trials (perhaps 100?) and draw better descriptive statistics across the the runs to get a more accurate picture of performance.
Cost: which version used more tokens, and roughly how much more? 
The Agent used roughly 3 times as many tokens, and the ouput was much more succinct and tight.
Reliability: which scored more consistently across runs? 
Both scored perfected against the rubrik, however the agent was much more compact and tight with it's answers.
One thing that surprised me:
I expected the performance difference to be greater--one or the other would drastically miss the mark.
Additionally, I found it easy to put together the pieces of both the workflow and the agent.
What I had to correct in code my agent wrote (AI-use disclosure — expected, not penalized): 
I had to manually configure my LITELLM_API_KEY environment variable after several retries using the bash scripts provided.
Additionally, the LLM crafted code for the workflow leveraged a TypeError and misused the chat(), so I had to ask Claw to rewrite and debug the error.

## Day 3 -- Build Challenge 1 : Tool/Function Calling
Key comparison between inefficient tool and token efficient tool. 
I build an upgraded search function that is token efficient, results are below:

[INEFFICIENT TOOL CALL]

 $ python3 bc1-tools/agent.py "tell me about the documents that contain the word Key_stopword in my notes?"
── step 1: request≈950 chars → chose search_notes {'query': 'Key_stopword'}
          tool returned 34 chars
── step 2: request≈1046 chars → chose search_notes_verbose {'query': 'Key_stopword'}
          tool returned 2475 chars
── step 3: request≈3591 chars → chose None {}
          tool returned 24 chars
── step 4: request≈4431 chars → chose list_notes {}
          tool returned 89 chars
── step 5: request≈4555 chars → chose search_notes_verbose {'query': 'Key_stopword'}
          tool returned 2475 chars
── step 6: request≈7100 chars → chose None {}
          tool returned 24 chars
── step 7: request≈7940 chars → chose finish {}

ANSWER: I found three documents containing the word 'Key_stopword': reading-summary.txt, capstone-brainstorm.txt, and standup-notes.txt. All three documents have 'Key_stopword' at the end of their content.

STATS: {'calls': 7, 'tokens': 7443, 'cache_hits': 0}

[EFFICIENT TOOL CALL]

repo $ python3 bc1-tools/agent.py "tell me about the documents that contain the word Key_stopword in my notes?"
── step 1: request≈1099 chars → chose search_notes {'query': 'Key_stopword'}
          tool returned 173 chars
── step 2: request≈1334 chars → chose read_note {'name': 'capstone-brainstorm.txt'}
          tool returned 1788 chars
── step 3: request≈3191 chars → chose read_note {'name': 'reading-summary.txt'}
          tool returned 245 chars
── step 4: request≈3501 chars → chose read_note {'name': 'standup-notes.txt'}
          tool returned 321 chars
── step 5: request≈3885 chars → chose None {}
          tool returned 24 chars
── step 6: request≈4784 chars → chose finish {}

ANSWER: I found three documents containing the word 'Key_stopword': 'capstone-brainstorm.txt', 'reading-summary.txt', and 'standup-notes.txt'. Each document has the word at the end.

STATS: {'calls': 6, 'tokens': 4551, 'cache_hits': 0}

[TOOL ANALYSIS]

We can see the improved tool reduced the total calls by 1 and tokens used by about 3000 tokens--  about a 40% reduction in tokens. Quite the improvement.

[DELEGATION LOG]

I prompted Claw with the following: "help me complete this assignment. we are working in the bc1-tools/ directory. before  
you begin, read the README.md file and the agent.py file in the that directory. become
familiar with the tasks. I want to implement a word counter, and a token-efficient    
search described below.                                                               
 TODO(you): add 2-3 custom tools. Ideas: word_count, a calculator,                    
 a token-efficient search that returns (filename, matching line) pairs,               
 a note-writer. Update TOOLS_SPEC and run_tool together — the spec is                 
 the model's only knowledge of your interface.   "

The model completed the tasks without error.
Additionally, I used Claude to create a short 500 word "product demo" for a silly product--a samurai sword for commuters on public transit. This file was used to test tool calling functionality of the agent.py. The Claude prompt is : "create a 500 word written sample about a fictious product demo. the product is a new japanese samurai sword for commuters on public transit. dont create a document, just paste the 500 words as a response and I'll copy pasta them."

For OpenClaw, I switched the model selection to OU Sandbox's Claude Sonet 4.6.
One thing I learned from this assignment is how easy it is to build simple tools for agents, and putting the pieces together in one symphony.

## BC4 -- EVAL 
What I Built

An evaluation harness for the LLM analysis node of ADReconAgent — the component that receives raw network enumeration output (nmap, ldapsearch, NetExec) and reasons about Active Directory attack surface. The harness runs entirely in the Codespace using fixture-based inputs. No nmap subprocess or AD infrastructure required — the fixtures ARE the tool output, making this the portable, evaluable slice of the full agent.

Target Function

target() calls the LLM analysis node with a system prompt loaded from prompts/ad_analysis.txt and the fixture as the user message. Temperature 0, caching on. This isolates and evaluates the reasoning layer specifically — the same node that will run inside LangGraph against GOAD in the full capstone. The system prompt and user message are combined into a single user turn to satisfy Bedrock-hosted model requirements on the OU LiteLLM Sandbox.

Error Analysis — What the Failures Taught Me

Final pass rate: 87% (threshold 80%)

Failure 1: empty-input-refusal
The model does not say "INSUFFICIENT DATA" verbatim on empty input — it produces a longer refusal explanation. This revealed that the system prompt's refusal instruction needs to be more forceful and the must_contain assertion needs to match the model's actual refusal language rather than an exact phrase. Lesson: test your refusal cases early — they expose prompt instruction gaps immediately.

Failure 2: format-severity-present
The model said "Domain Admins" rather than "domain admin" — a pluralization mismatch that the lowercased assertion didn't catch because the substring check requires the exact string. Lesson: must_contain strings should use the shortest unambiguous substring, not a full phrase that might vary in form.

Failure 3: multi-host-prioritization
The model referred to the service account differently than the fixture string "sqlservice" — using "SQL Service" or a variation. Lesson: when testing proper nouns from fixtures, use the shortest distinctive substring rather than the full token as it appears in the input.

Systemic finding — assertion layer vs judge layer:
The most reliable failure signal is the assertion layer. Moving qualitative requirements from judge criteria into must_not_contain strings (where possible) produced more consistent and cheaper detection. The judge layer is most valuable for qualitative questions — prioritization quality, explanation clarity — where assertions cannot express the requirement. When judge max_tokens was too low (150), JSON responses truncated mid-object causing unparseable verdicts. 250-400 tokens is the safe minimum for judge calls.

WAF content filtering:
The OU LiteLLM Sandbox WAF blocked requests containing "penetration" in the prompt. All instances were replaced with "security auditor" and "security assessment." This is an important operational lesson for building in institutional environments — content filters are invisible until they hit and the 403 error is not descriptive.

Prompt file naming:
A typo in the filename (ad analysis.txt vs ad_analysis.txt) caused the harness to silently fall back to the minimal inline prompt, producing degraded outputs for several runs. Lesson: validate that prompt files load correctly at startup with an explicit check rather than a silent fallback.

Delegation Log

AI used: Claude Sonnet 4.6

My key prompts:

"Help me design eval cases covering the real failure modes of an AD recon LLM analysis node"
"Write the harness.py target() function to call the LLM analysis node using the common/llm.py scaffold"
"Rewrite cases.jsonl with these specific fixes based on the observed failures"

What it got wrong:

Initial cases were too easy — all passed on first run. I had to add adversarial cases based on my own pentesting knowledge of real failure modes
Judge criteria were initially too lenient — Claude wrote criteria that passed outputs I would have labeled FAIL. I rewrote criteria for several cases based on my hand labels
Binary garbage characters in the garbage-input-refusal case caused JSON parse errors — had to replace with safe ASCII equivalents
must_contain strings were too literal — "serviceprincipalname" instead of "spn", "penetration tester" instead of "security auditor"

What I Would Do Differently
Design adversarial cases first. The easy cases provide coverage but the value is in cases that actually fail and expose real agent weaknesses.
Test refusal cases in isolation before integrating — they expose prompt instruction gaps immediately and cheaply.
Use shortest unambiguous substrings in must_contain rather than full phrases that vary in form across model outputs.
Validate prompt file loading explicitly at startup rather than relying on silent fallback behavior.
Replace fixture data with actual GOAD output once the lab is provisioned — ground-truth data produces more meaningful eval results than synthesized fixtures.

## BC5-Observability 

BC5 crystallized something important about observability design that connects directly to my capstone: the trace is only as good as your failure coverage. A trace that stops at the first exception tells you that something failed but not what — exactly the situation quiet_agent.py was designed to demonstrate. Adding failure events to every step before re-raising is the agentic equivalent of structured exception logging in traditional software — you need the context at the point of failure, not just the traceback. In a way, it's important to capture the 'state' of the machine as well as execution details. Eric Brandywine discusses how Amazon Security Engineers prefer this over traditional HITL approach (LINK: https://www.theregister.com/security/2026/06/20/why-amazon-hates-human-in-the-loop-ai-governance/5258639). While I think he get's some things wrong, he does raise some good points.

The HITL gate design also connects to the Brandwine accountability argument. Logging the human's raw input ("y" or "n") alongside the cost context means the trace records not just what the human decided but what information they had when they decided it. That's a richer audit trail than a boolean approval flag, and it's the pattern I'll carry forward into the capstone's checkpoint design--it adds fuller details around usage, observability, and errors.

The cost reconciliation gap — gateway log not found, falling back to STATS — is actually a meaningful observability finding in itself. It means there's a layer of the system (the gateway's view of token consumption) that I can't directly observe from my code. In a production deployment, that gap would need to be closed — either by ensuring gateway log access or by adding a gateway API call to pull usage directly.