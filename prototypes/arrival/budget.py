# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python-headless", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa", "pyobjc-framework-ApplicationServices"]
# ///
"""PROTOTYPE, throwaway. Loop plus frame arrival with zero processing, per camera state and format (#25).

  uv run budget.py

Loop latency: the mirror sessions' arrow warps (../mirror/results, #23), stamp before the call to the stamp of the
first frame at half contrast. Arrival: this prototype's sweeps, arrival in Python minus stamp, by camera state.
The two are resampled independently, as #23 did. Assumes the stamp marks the same instant of the exposure in every
camera state: unverified.
"""

import glob
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "mirror"))
import mirror  # noqa: E402

from arrival import COLS, I, slow  # noqa: E402

rng = np.random.default_rng(0)
loop, slow_mirror = [], []
for p in sorted(glob.glob(str(HERE.parent / "mirror/results/*loop.json"))):
    res = json.loads(Path(p).read_text())
    for t in res["trials"]:
        f = np.array(t["frames"], float)
        if len(f):
            slow_mirror += list(1000 * (f[:, 1] - f[:, 0]))
        if t["kind"] == "arrow" and t["call"] == "warp":
            s = mirror.score(t)
            if s is not None and (s[1] >= 0.5).any():
                loop.append(1000 * s[0][np.argmax(s[1] >= 0.5)])
loop = np.array(loop)
print(f"loop, arrow warp: n {len(loop)}  p50 {np.percentile(loop, 50):.1f}  p95 {np.percentile(loop, 95):.1f} ms")

arr = {}
for p in sorted(glob.glob(str(HERE / "results/*sweep.json"))):
    d = json.loads(Path(p).read_text())
    mains = "-22" in Path(p).name  # the second sweep ran on mains power, the first on battery
    for c in d["captures"]:
        r = np.array(c["rows"])
        if r.ndim != 2 or r.shape[1] <= I["width"] or len(r) < 60 or c["name"].startswith(("fps", "1280x720 fps")):
            continue
        r = r[r[:, 0] > r[0, 0] + 1.0]
        w = int(np.median(r[:, I["width"]]))
        h = {1920: 1080, 1280: 720, 640: 480}.get(w)
        if h is None or (w == 1920 and c["state"]["format"] != "1920x1080"):
            continue
        a = 1000 * (r[:, 1] - r[:, 0])
        m = slow(r)
        on = np.isfinite(r[:, I["sifr_exposure"]])
        arr.setdefault((f"{w}x{h}", "slow", "mains"), []).extend(a[m])
        arr.setdefault((f"{w}x{h}", "fast, second exposure", "mains"), []).extend(a[on & ~m])
        arr.setdefault((f"{w}x{h}", "fast, no second exposure", "mains"), []).extend(a[~on])
arr[("1920x1080", "slow", "mains, the mirror sessions")] = slow_mirror

print(f"\n{'format':<10} {'camera state':<26} {'power':<28} {'frames':>6} | arrival p5   p50   p95 | loop + arrival p50   p95  over 100 ms")
for (fmt, state, power), a in sorted(arr.items()):
    a = np.array(a)
    if len(a) < 100:
        continue
    tot = rng.choice(loop, 200000) + rng.choice(a, 200000)
    q = np.percentile(a, [5, 50, 95])
    print(f"{fmt:<10} {state:<26} {power:<28} {len(a):>6} |       {q[0]:5.1f} {q[1]:5.1f} {q[2]:5.1f} |              "
          f"{np.percentile(tot, 50):6.1f} {np.percentile(tot, 95):5.1f}  {100 * (tot > 100).mean():4.0f}%")
