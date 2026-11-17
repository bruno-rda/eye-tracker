# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "mediapipe==1.2.2", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""PROTOTYPE, throwaway. The controller of refine.py replayed on the pilot's cached landmarks (#21).

  uv run sim.py ../../recordings/pilot/<session> [--g-lo 1.5 ...]

No one steers here: the pilot's eyes went to a fixation target and the head did what it naturally
does. So this shows what the cursor does unasked, per facial feature:
  still   the 30 frames after each press, eyes on the target: how far the cursor wanders
  shift   a jump simulated --jump-ms after each target appears, up to the press: how far the gaze
          shift's own head movement drags the cursor, and when the rest rule lets the head in
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from refine import FEATURES, Controller, Params, q

ap = argparse.ArgumentParser()
ap.add_argument("session", type=Path)
for k, v in asdict(Params()).items():
    if not isinstance(v, (bool, str)):
        ap.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v)
a = ap.parse_args()
p = Params(**{k: getattr(a, k) for k in asdict(Params()) if hasattr(a, k)})
d = a.session.resolve()
lm = np.load(d / "features.npz")["lm"].astype(float)
pts = np.loadtxt(d / "frames.csv", delimiter=",", ndmin=2)[:, 0]
fix = {}
for e in map(json.loads, (d / "events.jsonl").read_text().splitlines()):
    if e["kind"] in ("target_on", "press") and e["block"] in ("early", "late"):
        fix.setdefault((e["block"], e["i"]), {})[e["kind"]] = e["t"]
fix = [f for f in fix.values() if len(f) == 2]
BIG = (-1e9, -1e9, 1e9, 1e9)


def run(f, i0, i1, jump_at=None, rest=True):
    """Cursor per frame from frame i0 to i1, a jump to the origin at frame jump_at; and the frame the head came in."""
    p.rest = rest
    c, C, t_in = Controller((0, 0), BIG), [], None
    for i in range(i0, i1):
        if i == jump_at:
            c.jump((0, 0), p)
        C.append(c.step(pts[i], f[i], p).copy())
        if jump_at is not None and i >= jump_at and t_in is None and not c.waiting:
            t_in = pts[i]
    return np.array(C), t_in


print(f"{d.name}: {len(fix)} fixations, gain {p.g_lo:g}-{p.g_hi:g} pt/px over {p.v_lo:g}-{p.v_hi:g} px/s, filter {p.mincut:g} Hz, "
      f"rest under {p.rest_speed:g} px/s for {p.rest_frames} frames, jump at {p.jump_ms:g} ms")
for name, idx in FEATURES.items():
    f = lm[:, idx].mean(1)
    still, drag, drag_rest, wait, never = [], [], [], [], 0
    for x in fix:
        i_on, i_j, i_p = (int(np.searchsorted(pts, t)) for t in (x["target_on"], x["target_on"] + p.jump_ms / 1000, x["press"]))
        if np.isnan(f[i_on - 30 : i_p + 30]).any() or i_p - i_j < 3:
            continue
        C, _ = run(f, i_p - 30, i_p + 30)
        still.append(np.linalg.norm(np.ptp(C[30:], axis=0)))
        C, _ = run(f, i_on - 30, i_p, i_j, rest=False)
        drag.append(np.linalg.norm(C[-1]))
        C, t_in = run(f, i_on - 30, i_p, i_j, rest=True)
        drag_rest.append(np.linalg.norm(C[-1]))
        never += t_in is None
        if t_in is not None:
            wait.append(t_in - pts[i_j])
    print(f"  {name:6} still: cursor range over 1 s p50 {q(still, 50)[0]} p90 {q(still, 90)[0]} pt | "
          f"shift, rest off: dragged p50 {q(drag, 50)[0]} p90 {q(drag, 90)[0]} pt | "
          f"rest on: dragged p50 {q(drag_rest, 50)[0]} p90 {q(drag_rest, 90)[0]} pt, head let in after p50 {q(wait, 50)[0]} p90 {q(wait, 90)[0]} s, never before the press {never}/{len(drag)}")
