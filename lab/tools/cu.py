#!/usr/bin/env python3
"""Desktop tool given to agents: logs each call, then runs the pinned cu.py.

cu_upstream.py is a copy of skills/linux-computer-use/scripts/cu.py from
https://github.com/arif481/linux-computer-use at commit 9c0dede.
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cu_upstream  # noqa: E402


def main():
    argv = sys.argv[1:]
    log = os.environ.get("LAB_ACTION_LOG")
    if log:
        with open(log, "a") as f:
            f.write(json.dumps({"t": round(time.time(), 3), "argv": argv}) + "\n")
    # `shot --out PATH` would let an agent write a file anywhere; screenshots stay in CU_DIR.
    # Parse exactly as cu.py does, so abbreviations like `--ou` are caught too.
    args = cu_upstream.build_parser().parse_args(argv)
    if getattr(args, "out", None) is not None:
        print("cu.py: --out is disabled in the benchmark; screenshots are saved automatically",
              file=sys.stderr)
        return 2
    return cu_upstream.main(argv)


if __name__ == "__main__":
    sys.exit(main())
