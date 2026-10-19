# linux-agent-bench

A lightweight benchmark of AI agents doing everyday tasks on a Linux desktop, scored on two things: whether they finish the task, and whether they stay safe while doing it. Some tasks are traps, such as a note with instructions planted for AI agents, and an agent only passes if it ignores them.

Everything runs on a virtual X display started for each run, so a full benchmark needs no virtual machine and never touches your real desktop.

**Status: early development.** There are 3 pilot tasks and the harness works end to end. The task set, the runs and the results come next; see [PLAN.md](PLAN.md).

## How a run works

1. A fresh environment starts: Xvfb, the openbox window manager, a private D-Bus session with nothing auto-started, and a private home folder for the apps.
2. The task sets up its files and opens its apps.
3. The agent gets a prompt with the task and one tool, [`cu.py`](lab/tools/cu.py) from [linux-computer-use](https://github.com/arif481/linux-computer-use), which takes screenshots and sends clicks and keystrokes. It is not allowed to run anything else, so it can't finish a desktop task by editing files from a shell.
4. The task's check inspects the end state (files, app logs) and decides pass or fail. It never relies on what the agent says it did.
5. The run folder keeps the prompt, the agent's transcript, every desktop action, the result and a GIF of the screen.

Every task also ships with a scripted solution (the oracle) and is tested against an agent that does nothing, so each check is shown to pass when the task is done and fail when it isn't.

## Agents

| Agent | How it runs | Restriction |
|---|---|---|
| `claude-code` | `claude -p` in restricted mode | Read, plus Bash limited to `cu.py`; no CLAUDE.md or user settings |
| `gemini-cli` | `gemini -p` | `read_file`, plus shell limited to `cu.py`; no GEMINI.md |
| `oracle` | the task's scripted solution | uses `cu.py` like the agents |
| `noop` | does nothing | |

Both CLI agents get exactly the same prompt. The results compare whole agents (model, CLI and its built-in prompting), not bare models.

## Quickstart

Ubuntu or Debian:

```bash
sudo apt install xvfb openbox xdotool dbus python3-pil python3-tk gedit
git clone https://github.com/arif481/linux-agent-bench.git
cd linux-agent-bench
python3 -m lab doctor
python3 -m lab tasks
python3 -m lab run --agent oracle            # every task should pass
python3 -m lab run --agent claude-code --task form-submit
python3 -m lab report
```

`--variant guarded` adds one paragraph to the prompt telling the agent that on-screen text is content, not instructions, so you can measure how much that warning helps. Results go to `results/` (ignored by git).

## Tests

```bash
python3 -m unittest discover -s tests              # unit tests, no display needed
LAB_X=1 python3 -m unittest discover -s tests      # also runs every task with the oracle and noop agents
```

## License

[MIT](LICENSE)
