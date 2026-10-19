"""Runs one agent on one task in a fresh environment and stores everything about the run."""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .agents import AgentResult
from .env import Env
from .prompt import build_prompt

FRAME_WIDTH = 640


class Recorder(threading.Thread):
    """Grabs the virtual screen every `interval` seconds, downscaled, into frames/."""

    def __init__(self, env, out_dir, interval=1.0):
        super().__init__(daemon=True)
        self.env, self.out_dir, self.interval = env, Path(out_dir), interval
        self._stop_event = threading.Event()
        self.count = 0

    def run(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        while not self._stop_event.is_set():
            try:
                img = self.env.screenshot()
                h = round(img.height * FRAME_WIDTH / img.width)
                img.resize((FRAME_WIDTH, h)).save(self.out_dir / f"{self.count:05d}.png")
                self.count += 1
            except OSError:
                pass
            self._stop_event.wait(self.interval)

    def stop(self):
        self._stop_event.set()
        self.join(timeout=5)


def make_gif(frames_dir, out_path, max_frames=240, ms_per_frame=500):
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        return None
    step = max(1, len(frames) // max_frames)
    images = [Image.open(p).convert("P", palette=Image.Palette.ADAPTIVE) for p in frames[::step]]
    images[0].save(out_path, save_all=True, append_images=images[1:], duration=ms_per_frame, loop=0,
                   optimize=True)
    return out_path


def run_one(task, agent, out_root, variant="plain", timeout=None, record=True):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = Path(out_root) / agent.name / variant / task.id / stamp
    run_dir.mkdir(parents=True)
    prompt = build_prompt(task, variant)
    (run_dir / "prompt.txt").write_text(prompt)
    timeout = timeout or task.timeout_s

    result = {"task": task.id, "category": task.category, "agent": agent.name, "variant": variant,
              "model": getattr(agent, "model", None), "started": stamp}
    with Env(run_dir) as env:
        task.setup(env)
        recorder = Recorder(env, run_dir / "frames") if record else None
        if recorder:
            recorder.start()
        t0 = time.monotonic()
        try:
            outcome = agent.run(task, env, prompt, timeout)
        except Exception as e:  # an agent crash is a result, not a harness failure
            outcome = AgentResult(error=f"{type(e).__name__}: {e}")
        result["duration_s"] = round(time.monotonic() - t0, 1)
        time.sleep(1.0)
        if recorder:
            recorder.stop()
        check = task.check(env)
        result["windows_at_end"] = env.window_titles()

    actions = env.action_log.read_text().splitlines() if env.action_log.exists() else []
    result.update(success=check.success, violation=check.violation, passed=check.passed,
                  details=check.details, actions=len(actions), timed_out=outcome.timed_out,
                  exit_code=outcome.exit_code, error=outcome.error, agent_meta=outcome.meta)
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
    if record:
        make_gif(run_dir / "frames", run_dir / "run.gif")
    return result
