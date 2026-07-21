# Agentic Systems Course Repo — SDI 4243/5243 (OU)

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Agentic-Systems-Summer-2026/collective-assignment-ballin-062)

> **⚠️ Two cautions.** (1) This button opens the Codespace **creation page with options** — enter your API key(s) in the "Recommended secrets" fields there *before* clicking Create. (2) In a brand-new student repo this badge still points at the course template until your first Codespace setup re-points it — so for your **first** launch, use the steps below instead of the badge.

Your personal course repository for the Summer 2026 July Block. Everything
you build this course lives here: five Build Challenges, your prompts, your
Build Journal, and a CI eval gate. By August 7 this repo *is* your portfolio.

## Get started (once)

1. Click **Use this template → Create a new repository** (your account;
   private is fine). Do **not** fork.
2. On your new repo: **Code → Codespaces → the "···" menu → New with
   options…** (skip the plain "Create codespace" button). The creation page
   shows two **Recommended secrets** — fill in whichever you have (either
   works; if you set both, LiteLLM is used first):
   `LITELLM_API_KEY` — your OU LiteLLM Sandbox key (starts with `sk-`),
   from your Sandbox invitation; or `OPENROUTER_API_KEY` — your OWN
   OpenRouter key (starts with `sk-or-`; create it at openrouter.ai —
   expect at most ~$10 of usage for the term). Then click **Create
   codespace**. (Forgot a key? No problem — the Gateway terminal will ask
   you for one on first start.)
3. When VS Code asks **"Do you want to allow automatic tasks…?"** (naming
   OpenClaw: Gateway and OpenClaw: TUI), click **Allow** — don't let it
   time out. That's what opens your two work terminals, and one click
   covers all future opens. Then wait for setup to finish (watch the
   numbered steps). The OpenClaw gateway auto-starts in the background and
   two terminals open: **Gateway** (live log) and **TUI** (chat with your
   agent). Full details on how this works:
   [openclaw-codespace-starter](https://github.com/jhassell/openclaw-codespace-starter)
   — this repo includes the same machinery.
   **No terminals appeared?** That's a VS Code security gate, not a broken
   setup: press `Cmd/Ctrl+Shift+P` → **Tasks: Run Task** → **OpenClaw:
   Gateway**, then again for **OpenClaw: TUI** (or just run
   `bash scripts/start-gateway.sh` in a terminal — it will prompt for your
   key if needed). If VS Code shows an "automatic tasks" notification
   (bell icon, bottom right), allow it so future opens start by themselves.
4. Smoke test: `python3 bc1-tools/agent.py "what do my notes say about the demo?"`

## Layout

| Path | What it is |
|---|---|
| `bc1-tools/` … `bc5-observability/` | One folder per Build Challenge: a runnable starter + `README.md` with the spec, acceptance check, and rubric |
| `common/llm.py` | Shared OpenRouter client (stdlib): `chat()`, `STATS` (cost tracking), `cache=True`, `load_prompt()` |
| `prompts/` + `PROMPTS.md` | Prompts as files + the required changelog. Prompts are software artifacts. |
| `JOURNAL.md` | Your Build Journal (graded, cumulative, also your AI-use disclosure record) |
| `shipday/` | Ship Day: `check.py` acceptance checker and `.env.example` for the Tavily + Netlify build |
| `.github/workflows/eval.yml` | CI regression gate — runs your BC4 eval harness on every push |
| `.devcontainer/`, `scripts/`, `.vscode/` | Codespace machinery (OpenClaw + OpenRouter) — you shouldn't need to touch these |

## Working rhythm

Each dated Canvas module tells you what to build. Build it in the matching
folder, commit as you go (small commits with real messages — your history is
part of the evidence), push, and add a `JOURNAL.md` entry. Due 11:59 PM CT.

### Getting instructor updates

Your repo is a **snapshot** of the template at the moment you created it —
instructor fixes pushed to the template afterward do *not* arrive
automatically, and plain `git pull` only syncs **your own** repo. If an
update is announced, run (first time):

```bash
git remote add upstream https://github.com/Agentic-Systems-Summer-2026/agentic-systems-course
git pull upstream main --allow-unrelated-histories
```

and after that just `git pull upstream main`. Grading and assignment
details never require this — they live in Canvas, not in the repo.

**Keys stay out of git.** Your endpoint key (LiteLLM or OpenRouter) lives in
Codespaces secrets and (from BC4 on) a GitHub Actions repository secret.
`.env` files are gitignored. If a key ever lands in a commit: rotate it
(tell the instructor if it's a Sandbox key), then fix history.

## CI eval gate (from BC4)

The included workflow runs `bc4-evals/` on every push — a small live sweep
(~5 cases, cached, capped). Until you add a `LITELLM_API_KEY` (or
`OPENROUTER_API_KEY`) repository secret it passes with a notice, so early
pushes stay green. From BC4 onward
a red X means your change regressed the evals — read the failure, fix or
justify, never just raise the threshold.

## Toolbelt (pre-installed)

Beyond Python/Node/git, setup installs: `cloudflared` (share a running demo:
`cloudflared tunnel --url http://localhost:5000`), `jq` (JSON wrangling),
`gh` (check your CI eval runs: `gh run list`), `sqlite3` (retrieval/memory
labs, agent state), `tmux` (keep long-running agents alive — BC3),
`asciinema` (terminal recordings — an official demo-evidence format:
`asciinema rec demo.cast`, then commit the file), `ripgrep`, `httpie`,
`tree`, `htop`, `entr` (auto-rerun on change:
`ls bc4-evals/*.py | entr python3 bc4-evals/harness.py`), and `flask`
(serve a capstone demo UI behind your tunnel).

## Model notes

Default: **`Claude Sonnet 4.6` on the OU LiteLLM Sandbox**, with
`Qwen3 Coder 30B` as an automatic fallback if the primary is unavailable. On
OpenRouter the default is `qwen/qwen3-coder`. The Codespace picks the endpoint
from your key(s) at startup (LiteLLM first).

**Why a large model by default.** Most of what you build this term is
multi-step tool use: call a tool, read the result, decide what to do next,
recover when something fails. Small coder models are not reliable at that, and
the way they fail is the problem — instead of stopping with an error, they tend
to invent a plausible result and report success. On the Ship Day assignment,
`Qwen3 Coder 30B` claimed it had no network access (it did), silently replaced
a real web search with five fabricated results, never deployed anything, and
finished with "Website Successfully Built!" above a list of green checkmarks
for work it had not done.

That is worth knowing for its own sake — it is the failure mode Day 13
(observability) and Day 14 (human oversight) are about. It is also why the
fallback matters: **if your agent starts inventing things or claiming it cannot
reach the network, check which model is actually answering.** You may have
failed over. The active model is shown in the TUI status bar.

**Switching models.** Run `scripts/select-model.sh` (or `Ctrl/Cmd+Alt+M`). It
asks which provider you want for your primary, shows that catalog, then asks
the same for your fallback, which you can decline. Primary and fallback may
come from different providers. To set one directly:

```bash
openclaw models set "litellm/Claude Sonnet 4.6"
openclaw models status
```

The quotes matter — these model ids contain spaces. Changes apply to new
sessions; inside a chat you are already in, switch with `/model`.

**Per-call routing.** Send individual calls to cheaper models with
`chat(..., model=...)` — you'll use that in the Day 9 cost lab.
