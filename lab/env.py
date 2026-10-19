"""An isolated X11 desktop for one benchmark run.

Each Env starts its own Xvfb display, openbox window manager and D-Bus
session, with a private HOME and XDG directories under the run folder.
Apps launched through it cannot reach the real desktop, and the agent only
ever sees this display.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from PIL import ImageGrab

TOOLS = Path(__file__).resolve().parent / "tools"
CU = TOOLS / "cu.py"
DEFAULT_SIZE = (1280, 800)
REQUIRED = ("Xvfb", "openbox", "xdotool", "dbus-daemon")
DBUS_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=/tmp</listen>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


class EnvError(RuntimeError):
    pass


def missing_programs(extra=()):
    return [p for p in (*REQUIRED, *extra) if shutil.which(p) is None]


def _free_display(start=90, end=200):
    for n in range(start, end):
        if not os.path.exists(f"/tmp/.X11-unix/X{n}") and not os.path.exists(f"/tmp/.X{n}-lock"):
            return n
    raise EnvError("no free X display number between :90 and :199")


def _wait_until(predicate, timeout, what):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise EnvError(f"timed out after {timeout}s waiting for {what}")


class Env:
    def __init__(self, root, size=DEFAULT_SIZE):
        self.root = Path(root)
        self.size = size
        self.work = self.root / "work"          # task files live here
        self.home = self.root / "home"          # HOME for apps
        self.agent_dir = self.root / "agent"    # agent working directory
        self.shots = self.agent_dir / "shots"   # CU_DIR: screenshots the agent reads
        self.logs = self.root / "logs"
        self.action_log = self.root / "actions.jsonl"
        self.display = None
        self._procs = []
        self._dbus_pid = None
        self._dbus_address = None

    # --- lifecycle ---------------------------------------------------------

    def __enter__(self):
        try:
            self.start()
        except BaseException:
            self.stop()  # don't leave a half-started Xvfb or D-Bus behind
            raise
        return self

    def __exit__(self, *exc):
        self.stop()

    def start(self):
        missing = missing_programs()
        if missing:
            raise EnvError("missing programs: " + ", ".join(missing))
        for d in (self.work, self.home, self.agent_dir, self.shots, self.logs,
                  self.root / "runtime", self.home / ".config", self.home / ".local/share",
                  self.home / ".cache"):
            d.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root / "runtime", 0o700)

        n = _free_display()
        self.display = f":{n}"
        w, h = self.size
        self._spawn("xvfb", ["Xvfb", self.display, "-screen", "0", f"{w}x{h}x24", "-nolisten", "tcp"],
                    env=os.environ.copy())
        _wait_until(lambda: os.path.exists(f"/tmp/.X11-unix/X{n}"), 10, "Xvfb")

        # A bare bus with no service directories: nothing can be auto-started on it, so calls to
        # desktop services (portals, dconf, gvfs) fail at once instead of hanging the app.
        dbus_conf = self.root / "dbus.conf"
        dbus_conf.write_text(DBUS_CONFIG)
        out = subprocess.run(["dbus-daemon", f"--config-file={dbus_conf}", "--fork", "--print-address=1",
                              "--print-pid=1"],
                             capture_output=True, text=True, env=self._base_env(), check=True)
        address, pid = out.stdout.split()[:2]
        self._dbus_address, self._dbus_pid = address, int(pid)

        self._spawn("openbox", ["openbox", "--sm-disable"], env=self.app_env())
        _wait_until(lambda: self.xdotool("get_desktop", check=False) != "", 10, "openbox")

    def stop(self):
        for proc in reversed(self._procs):
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for proc in self._procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
        self._procs.clear()
        if self._dbus_pid:
            try:
                os.kill(self._dbus_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            self._dbus_pid = None

    # --- environments for child processes -----------------------------------

    def _base_env(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "SESSION_MANAGER")}
        env.update(DISPLAY=self.display or "", XDG_SESSION_TYPE="x11", GDK_BACKEND="x11",
                   NO_AT_BRIDGE="1")
        return env

    def app_env(self):
        """Environment for apps under test: private HOME, XDG dirs and D-Bus."""
        env = self._base_env()
        env.update(HOME=str(self.home),
                   XDG_CONFIG_HOME=str(self.home / ".config"),
                   XDG_DATA_HOME=str(self.home / ".local/share"),
                   XDG_CACHE_HOME=str(self.home / ".cache"),
                   XDG_RUNTIME_DIR=str(self.root / "runtime"),
                   DBUS_SESSION_BUS_ADDRESS=self._dbus_address or "",
                   GSETTINGS_BACKEND="memory", GTK_USE_PORTAL="0")
        return env

    def agent_env(self):
        """Environment for the agent process: real HOME (for its login), this display."""
        env = self._base_env()
        env.update(CU_DIR=str(self.shots), LAB_ACTION_LOG=str(self.action_log))
        return env

    # --- helpers for tasks ---------------------------------------------------

    def _spawn(self, name, argv, env, cwd=None):
        log = open(self.logs / f"{name}.log", "ab")
        proc = subprocess.Popen(argv, env=env, cwd=cwd or self.work, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        self._procs.append(proc)
        return proc

    def launch(self, argv, name=None, wait_title=None, timeout=20):
        """Start an app on this display; optionally wait for a window whose title matches."""
        proc = self._spawn(name or Path(argv[0]).name, argv, env=self.app_env())
        if wait_title:
            _wait_until(lambda: self.find_window(wait_title) is not None, timeout, f"window /{wait_title}/")
            time.sleep(0.5)  # let it finish drawing
        return proc

    def launch_python(self, script, *args, **kw):
        return self.launch([sys.executable, str(script), *map(str, args)], name=Path(script).stem, **kw)

    def xdotool(self, *args, check=True):
        r = subprocess.run(["xdotool", *map(str, args)], capture_output=True, text=True,
                           env=self._base_env())
        if check and r.returncode != 0:
            raise EnvError(f"xdotool {' '.join(map(str, args))}: {r.stderr.strip()}")
        return r.stdout.strip() if r.returncode == 0 else ""

    def find_window(self, title_regex):
        ids = self.xdotool("search", "--onlyvisible", "--name", title_regex, check=False).split()
        return ids[-1] if ids else None

    def window_titles(self):
        ids = self.xdotool("search", "--onlyvisible", "--name", ".", check=False).split()
        return [t for t in (self.xdotool("getwindowname", i, check=False) for i in ids) if t]

    def active_title(self):
        return self.xdotool("getactivewindow", "getwindowname", check=False)

    def focus(self, title_regex):
        wid = self.find_window(title_regex)
        if wid is None:
            raise EnvError(f"no window matching /{title_regex}/")
        self.xdotool("windowactivate", "--sync", wid)

    def cu(self, *args):
        """Run the desktop tool exactly as an agent would (used by the oracle)."""
        r = subprocess.run([sys.executable, str(CU), *map(str, args)], capture_output=True, text=True,
                           env=self.agent_env())
        if r.returncode != 0:
            raise EnvError(f"cu.py {' '.join(map(str, args))}: {r.stderr.strip()}")
        return r.stdout

    def screenshot(self):
        return ImageGrab.grab(xdisplay=self.display)


def matches(pattern, text):
    return re.search(pattern, text or "", re.I) is not None
