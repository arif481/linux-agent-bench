"""Agents that can attempt a task. Each has a name and run(task, env, prompt, timeout)."""
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

from ..env import CU


@dataclass
class AgentResult:
    exit_code: Optional[int] = None
    timed_out: bool = False
    error: Optional[str] = None
    meta: dict = field(default_factory=dict)


class NoopAgent:
    """Does nothing. Every task's check must fail against it."""
    name = "noop"

    def run(self, task, env, prompt, timeout):
        return AgentResult(exit_code=0)


class OracleAgent:
    """Runs the task's scripted solution through the same desktop tool agents use."""
    name = "oracle"

    def run(self, task, env, prompt, timeout):
        if task.oracle is None:
            return AgentResult(error="task has no oracle")
        task.oracle(env)
        time.sleep(1.0)  # let the app finish writing
        return AgentResult(exit_code=0)


def _run_cli(argv, env, cwd, transcript_path, timeout, extra_env=None):
    proc_env = env.agent_env()
    proc_env.update(extra_env or {})
    with open(transcript_path, "wb") as out, open(env.logs / "agent-stderr.log", "wb") as err:
        proc = subprocess.Popen(argv, cwd=cwd, env=proc_env, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            return AgentResult(exit_code=proc.wait(timeout=timeout))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            return AgentResult(exit_code=proc.returncode, timed_out=True)


class ClaudeCodeAgent:
    """Claude Code in print mode, restricted to Read and the cu.py Bash commands."""
    name = "claude-code"

    def __init__(self, model=None):
        self.model = model

    def argv(self, prompt):
        argv = ["claude", "-p", prompt,
                "--output-format", "stream-json", "--verbose",
                "--restricted", "--tools", "Bash,Read",
                "--allowedTools", f"Bash(python3 {CU}:*)", "Read",
                "--permission-mode", "dontAsk",
                "--no-session-persistence"]
        if self.model:
            argv += ["--model", self.model]
        return argv

    def run(self, task, env, prompt, timeout):
        transcript = env.root / "transcript.jsonl"
        result = _run_cli(self.argv(prompt), env, env.agent_dir, transcript, timeout)
        result.meta = parse_claude_transcript(transcript)
        return result


def parse_claude_transcript(path):
    meta = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return meta
    for line in lines:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("type") == "system" and msg.get("subtype") == "init":
            meta["model"] = msg.get("model")
        if msg.get("type") == "result":
            meta.update(num_turns=msg.get("num_turns"), duration_ms=msg.get("duration_ms"),
                        is_error=msg.get("is_error"), usage=msg.get("usage"),
                        total_cost_usd=msg.get("total_cost_usd"), final=msg.get("result"))
    return meta


class GeminiCliAgent:
    """Gemini CLI in headless mode; system settings limit its tools to read_file and cu.py."""
    name = "gemini-cli"

    def __init__(self, model=None):
        self.model = model

    def settings(self):
        return {
            "tools": {"core": [f"run_shell_command(python3 {CU})", "read_file"]},
            # Load no GEMINI.md memory (a name no file uses) and no directory listing, so the
            # agent sees only the benchmark prompt, as Claude Code does in --restricted mode.
            "context": {"fileName": ["LAB_BENCH_NO_CONTEXT.md"], "includeDirectoryTree": False},
        }

    def argv(self, prompt):
        argv = ["gemini", "-p", prompt, "--output-format", "json", "--approval-mode", "yolo"]
        if self.model:
            argv += ["--model", self.model]
        return argv

    def run(self, task, env, prompt, timeout):
        settings_path = env.root / "gemini-system-settings.json"
        settings_path.write_text(json.dumps(self.settings(), indent=2))
        transcript = env.root / "transcript.json"
        result = _run_cli(self.argv(prompt), env, env.agent_dir, transcript, timeout,
                          extra_env={"GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(settings_path),
                                     "GEMINI_CLI_TRUST_WORKSPACE": "true"})
        try:
            data = json.loads(transcript.read_text() or "{}")
            result.meta = {"stats": data.get("stats"), "final": data.get("response"),
                           "error": data.get("error")}
        except (OSError, ValueError):
            pass
        return result


AGENTS = {
    "noop": NoopAgent,
    "oracle": OracleAgent,
    "claude-code": ClaudeCodeAgent,
    "gemini-cli": GeminiCliAgent,
}


def make_agent(name, model=None):
    if name not in AGENTS:
        raise ValueError(f"unknown agent {name!r}; choose from {', '.join(AGENTS)}")
    cls = AGENTS[name]
    return cls(model=model) if name in ("claude-code", "gemini-cli") else cls()
