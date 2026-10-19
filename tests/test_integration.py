"""Runs every task on a real virtual display with the oracle and noop agents.

Needs Xvfb, openbox, xdotool, dbus-daemon, gedit and python3-tk. Skipped unless LAB_X=1.
"""
import glob
import os
import tempfile
import unittest

from lab.agents import NoopAgent, OracleAgent
from lab.runner import run_one
from lab.task import load_tasks


@unittest.skipUnless(os.environ.get("LAB_X") == "1", "set LAB_X=1 to run tasks on a virtual display")
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.locks_before = set(glob.glob("/tmp/.X*-lock"))

    def tearDown(self):
        leaked = set(glob.glob("/tmp/.X*-lock")) - self.locks_before
        self.assertEqual(leaked, set(), "an Xvfb display was left running")

    def test_oracle_passes_every_task(self):
        for task in load_tasks().values():
            with self.subTest(task=task.id):
                r = run_one(task, OracleAgent(), self.tmp.name, record=False)
                self.assertTrue(r["passed"], r)
                self.assertGreater(r["actions"], 0, "the oracle must act through cu.py")

    def test_noop_fails_every_task(self):
        for task in load_tasks().values():
            with self.subTest(task=task.id):
                r = run_one(task, NoopAgent(), self.tmp.name, record=False)
                self.assertFalse(r["passed"], r)
                self.assertIsNone(r["violation"])


if __name__ == "__main__":
    unittest.main()
