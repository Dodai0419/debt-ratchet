"""Reproduce the README numbers: python bench/bench.py /path/to/ponytail-checkout"""
import statistics
import subprocess
import sys
import time
from pathlib import Path

repo, tool = sys.argv[1], str(Path(__file__).resolve().parent.parent / "debt_ratchet.py")


def med(cmd, n=7):
    ts = []
    for _ in range(n):
        s = time.perf_counter()
        r = subprocess.run(cmd, cwd=repo, capture_output=True)
        ts.append(time.perf_counter() - s)
    return statistics.median(ts) * 1000, r


g, r = med(["git", "grep", "--no-index", "--exclude-standard", "-nE", "(#|//|/[*]) ?(shortcut|ponytail):"])
m, out = med([sys.executable, tool, "ledger", "."])
print(f"git grep step: {g:.0f} ms ({len(r.stdout.splitlines())} hits)")
print(f"debt-ratchet ledger: {m:.0f} ms ({out.stdout.decode().strip().splitlines()[-1]})")
