"""Task definition and loading.

A task module in tasks/ defines a module-level ``TASK = Task(...)``. The
check function inspects the end state (files, app logs, windows) and never
trusts what the agent says it did.
"""
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

TASKS_DIR = Path(__file__).resolve().parent.parent / "tasks"
APPS = Path(__file__).resolve().parent / "apps"


@dataclass
class Check:
    success: bool
    violation: Optional[str] = None   # set when the agent did something it must not do
    details: str = ""

    @property
    def passed(self):
        return self.success and self.violation is None


@dataclass
class Task:
    id: str
    instruction: str
    setup: Callable
    check: Callable
    oracle: Optional[Callable] = None
    category: str = "capability"      # "capability" or "safety"
    timeout_s: int = 300
    tags: tuple = field(default_factory=tuple)


def load_tasks(directory=TASKS_DIR):
    tasks = {}
    for path in sorted(Path(directory).glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"lab_tasks.{path.stem}", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        task = getattr(module, "TASK", None)
        if not isinstance(task, Task):
            raise ValueError(f"{path} does not define TASK = Task(...)")
        if task.id in tasks:
            raise ValueError(f"duplicate task id {task.id!r}")
        tasks[task.id] = task
    return tasks
