# Plan

Goal: a small, reproducible benchmark of off-the-shelf agents (Claude Code, Gemini CLI, an open vision model) doing Linux desktop tasks, scored for success and for safety, with real numbers, failure analysis and GIFs of actual runs. Budget: no money beyond existing Claude and Google subscriptions; open-model runs on Colab's free GPU.

## Phases

### 1. Research and harness (weeks 1–2)

- [x] Isolated environment per run: Xvfb, openbox, private D-Bus with no service activation, private HOME and XDG dirs
- [x] Task format with setup, instruction, check and an oracle solution
- [x] `cu.py` wrapper that logs every action
- [x] Agents: noop, oracle, Claude Code, Gemini CLI
- [x] Prompt variants: `plain` and `guarded`
- [x] Recording to frames and GIF
- [x] Unit tests, plus integration tests that run every task with oracle and noop
- [x] First real run: Claude Code passed `form-submit`
- [ ] Sign in to Gemini CLI and run it on the pilot tasks
- [ ] Probe that Gemini CLI cannot run anything except `cu.py` and does not load GEMINI.md. Its shell allowlist is a prefix rule, so test redirection, pipes, `$(...)` and backticks before any real run, as was done for Claude Code
- [ ] Consider exposing the desktop as an MCP server (structured `shot`, `click`, `type` tools that return images) so neither agent needs a shell at all; this removes the allowlist question and gives both agents an identical interface
- [ ] Read OSWorld, WindowsAgentArena and recent prompt-injection benchmarks for agents; write down what this benchmark adds or narrow its scope
- [ ] Check the current usage limits for unattended `claude -p` on the subscription and for Gemini CLI's free tier, and confirm automated benchmark runs are within each product's terms
- [x] CI running the integration tests on Ubuntu 22.04 and 24.04

### 2. Tasks (weeks 3–4)

- [ ] About 40 tasks: text editing, files, settings, a browser on local pages (no internet), multi-app workflows
- [ ] About 10 safety tasks: planted instructions in documents, web pages and notifications; requests that should be confirmed first; input aimed at the wrong window
- [ ] Every task passes with the oracle and fails with noop in CI
- [ ] Difficulty labels from a first round of runs

### 3. Runs (weeks 5–6)

- [ ] Claude Code and Gemini CLI, both prompt variants, 3 runs per task
- [ ] Open model (Qwen2.5-VL-7B or similar) through a small agent loop, running fully inside Colab
- [ ] Spread runs over days to stay within usage limits

### 4. Analysis and release (weeks 7–8)

- [ ] Success and safety rates with confidence intervals
- [ ] Failure taxonomy from the transcripts and GIFs
- [ ] Results page on GitHub Pages, README write-up, demo GIFs
- [ ] Stretch: arXiv preprint; instructions for submitting another agent

## Design decisions

- **Agents act only through the desktop.** Claude Code runs with `--restricted --tools Bash,Read`, Bash limited to `python3 lab/tools/cu.py`, and `--permission-mode dontAsk`. Gemini CLI gets a system settings file (via `GEMINI_CLI_SYSTEM_SETTINGS_PATH`, which overrides all other settings) limiting tools to `read_file` and `run_shell_command(python3 lab/tools/cu.py)`.
- **No personal context.** Restricted mode keeps CLAUDE.md and user settings out of Claude Code. Gemini CLI is pointed at a context file name that doesn't exist, so it loads no GEMINI.md.
- **Checks read state, never the agent's claims.** Files on disk and app event logs decide pass and fail.
- **Security boundaries, tested.** The virtual display needs a per-run cookie, so other processes on the machine can't connect to it. `shot --out` is refused by the wrapper. A probe of Claude Code's allowlist found redirection, pipes, `$(...)`, backticks and substitution inside arguments all refused.
- **Fairness caveat.** The two CLIs differ in more than the model, so results describe whole agents.

## Log

- **2026-10-19.** Harness built. gedit hung on start because the private D-Bus session auto-started `xdg-desktop-portal-gtk`; a bus config with no service directories plus `GSETTINGS_BACKEND=memory` fixed it (window in 0.8 s). Oracle passes all 3 pilot tasks and noop fails all 3. Claude Code (claude-opus-5-5) passed `form-submit` in 21.8 s with 9 desktop actions over 7 turns. A probe confirmed the permission boundary: 5 of 5 forbidden shell commands were refused, including compound commands that hid a forbidden part behind `cu.py`, and so was a read outside the run folder; Claude Code reported no CLAUDE.md or user memory in its context.
- **2026-10-19, later.** A security review flagged an open X display, file writes through `shot --out`, and reliance on shell-prefix allowlists. Fixed the first two with an Xauthority cookie and a wrapper check, both covered by tests. Claude Code's allowlist held against every bypass tried; Gemini CLI's is untested until it is signed in.
