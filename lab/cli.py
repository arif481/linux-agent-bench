"""Command line: list tasks, check the environment, run agents, summarise results."""
import argparse
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from .agents import AGENTS, make_agent
from .env import missing_programs
from .prompt import VARIANTS
from .runner import run_one
from .task import load_tasks


def cmd_tasks(args):
    for task in load_tasks().values():
        print(f"{task.id:22} {task.category:10} {task.instruction}")


def cmd_doctor(args):
    ok = True
    missing = missing_programs(extra=("gedit",))
    print("programs: " + ("ok" if not missing else "missing " + ", ".join(missing)))
    ok &= not missing
    for cli in ("claude", "gemini"):
        print(f"{cli}: " + ("found" if shutil.which(cli) else "not installed (only needed for that agent)"))
    try:
        import tkinter  # noqa: F401
        print("tkinter: ok")
    except ImportError:
        print("tkinter: missing (sudo apt install python3-tk)")
        ok = False
    return 0 if ok else 1


def cmd_run(args):
    tasks = load_tasks()
    selected = list(tasks.values()) if args.task == ["all"] else [tasks[t] for t in args.task]
    agent = make_agent(args.agent, model=args.model)
    failures = 0
    for task in selected:
        for i in range(args.repeat):
            r = run_one(task, agent, args.out, variant=args.variant, timeout=args.timeout,
                        record=not args.no_record)
            mark = "PASS" if r["passed"] else "FAIL"
            extra = f" violation: {r['violation']}" if r["violation"] else ""
            print(f"{mark} {agent.name:12} {task.id:22} run {i + 1}/{args.repeat} "
                  f"{r['duration_s']:6.1f}s {r['actions']:3d} actions | {r['details']}{extra}")
            failures += not r["passed"]
    return 0 if args.expect != "pass" or failures == 0 else 1


def cmd_report(args):
    stats = defaultdict(lambda: {"runs": 0, "passed": 0, "success": 0, "violations": 0})
    for path in Path(args.results).rglob("result.json"):
        r = json.loads(path.read_text())
        key = (r["agent"], r.get("variant", "plain"), r["task"])
        s = stats[key]
        s["runs"] += 1
        s["passed"] += r["passed"]
        s["success"] += r["success"]
        s["violations"] += bool(r["violation"])
    if not stats:
        print("no results found")
        return 1
    header = ("agent", "variant", "task", "runs", "passed", "success", "violations")
    print("{:14} {:8} {:22} {:>4} {:>6} {:>7} {:>10}".format(*header))
    for (agent, variant, task), s in sorted(stats.items()):
        print(f"{agent:14} {variant:8} {task:22} {s['runs']:4d} {s['passed']:6d} {s['success']:7d} "
              f"{s['violations']:10d}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="lab", description="Linux agent benchmark")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("tasks", help="list tasks").set_defaults(func=cmd_tasks)
    doctor = sp.add_parser("doctor", help="check that the required programs are installed")
    doctor.set_defaults(func=cmd_doctor)

    r = sp.add_parser("run", help="run an agent on tasks")
    r.add_argument("--agent", required=True, choices=list(AGENTS))
    r.add_argument("--task", nargs="+", default=["all"])
    r.add_argument("--variant", choices=VARIANTS, default="plain")
    r.add_argument("--model")
    r.add_argument("--repeat", type=int, default=1)
    r.add_argument("--timeout", type=int, help="seconds per run (default: the task's own limit)")
    r.add_argument("--out", default="results")
    r.add_argument("--no-record", action="store_true", help="skip frames and the GIF")
    r.add_argument("--expect", choices=["pass", "any"], default="any",
                   help="exit non-zero unless every run passes (for CI)")
    r.set_defaults(func=cmd_run)

    rep = sp.add_parser("report", help="summarise results")
    rep.add_argument("results", nargs="?", default="results")
    rep.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
