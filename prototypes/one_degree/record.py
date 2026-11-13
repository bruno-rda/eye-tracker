# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""PROTOTYPE, throwaway. Records raw frames for the one-degree question (#8).

  uv run record.py formats                          # 10 frames per capture format, gaze on the centre target
  uv run record.py fixations --size 1920x1080 --distance-cm 55

Fixations: a bullseye appears; look at its centre, keep the head still, press space.
The next 30 frames are kept and the target turns green while they record. r redoes the last target, esc quits.
Frames land in recordings/one-degree/ (gitignored), uncompressed NV12.
"""

import argparse
import json
import math
import random
import threading
import time
import queue
from datetime import datetime
from pathlib import Path

import AppKit
import cv2
import numpy as np

from capture import Camera, device, formats

ROOT = Path(__file__).resolve().parents[2] / "recordings" / "one-degree"
SCREEN_CM = (30.24, 19.64)  # 3024 x 1964 px at 254 ppi (Apple tech specs, MacBook Pro 14-inch)
WIN = "one-degree"


def screen():
    f = AppKit.NSScreen.mainScreen().frame().size
    return f.width, f.height


def window():
    """Fullscreen; returns the content rect in points, top-left origin. Below the notch strip on this machine."""
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    for _ in range(100):  # let the fullscreen transition settle
        cv2.imshow(WIN, np.zeros((10, 10, 3), np.uint8))
        cv2.waitKey(20)
    f = max((w.frame() for w in AppKit.NSApp().windows()), key=lambda f: f.size.width * f.size.height)
    x, y, w, h = f.origin.x, f.origin.y, f.size.width, f.size.height
    return int(x), int(screen()[1] - y - h), int(w), int(h)


def bullseye(img, x, y, r, colour):
    cv2.circle(img, (x, y), r, colour, -1, cv2.LINE_AA)
    cv2.line(img, (x - r, y), (x + r, y), (0, 0, 0), max(1, r // 6), cv2.LINE_AA)
    cv2.line(img, (x, y - r), (x, y + r), (0, 0, 0), max(1, r // 6), cv2.LINE_AA)
    cv2.circle(img, (x, y), max(2, r // 4), colour, -1, cv2.LINE_AA)


def writer():
    q = queue.Queue()

    def run():
        while (job := q.get()) is not None:
            path, kw = job
            np.savez(path, **kw)

    t = threading.Thread(target=run)
    t.start()
    return q, t


def text(img, s):
    cv2.putText(img, s, (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2, cv2.LINE_AA)


def run_formats(args):
    out = ROOT / f"formats-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    rx, ry, rw, rh = window()
    sizes = sorted(formats(device()), key=lambda s: s[0] * s[1])
    meta = {"kind": "formats", "distance_cm": args.distance_cm, "captures": []}
    for size in sizes:
        cam = Camera(size).start()
        t0, frames, pts = time.monotonic(), [], []
        while len(frames) < 10:
            img = np.zeros((rh, rw, 3), np.uint8)
            text(img, f"look at the target  {size[0]}x{size[1]}")
            bullseye(img, rw // 2, rh // 2, 14, (255, 255, 255))
            cv2.imshow(WIN, img)
            if cv2.waitKey(5) == 27:
                return
            while not cam.q.empty():
                t, f = cam.q.get()
                if t - t0 > 1.5:  # exposure settles after the session starts
                    frames.append(f), pts.append(t)
        state = cam.state()
        cam.stop()
        name = f"{size[0]}x{size[1]}.npz"
        np.savez(out / name, nv12=np.stack(frames[:10]), pts=np.array(pts[:10]))
        meta["captures"].append({"file": name, "camera": state})
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(out)


def run_fixations(args):
    size = tuple(map(int, args.size.split("x")))
    out = ROOT / f"fixations-{size[0]}x{size[1]}-{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    rx, ry, rw, rh = window()
    sw, sh = screen()
    cm_per_pt = SCREEN_CM[0] / sw
    d = args.distance_cm
    r = max(4, round(math.tan(math.radians(0.3)) * d / cm_per_pt))  # 0.6 deg target

    grid = [(fx, fy) for fy in (0.1, 0.5, 0.9) for fx in (0.08, 0.29, 0.5, 0.71, 0.92)] * args.reps
    random.shuffle(grid)
    targets = []
    for fx, fy in grid:
        x_cm = (rx + fx * rw) * cm_per_pt - SCREEN_CM[0] / 2
        y_cm = (ry + fy * rh) * cm_per_pt - SCREEN_CM[1] / 2
        targets.append({
            "fx": fx, "fy": fy, "x_cm": x_cm, "y_cm": y_cm,
            "deg": [math.degrees(math.atan2(x_cm, d)), math.degrees(math.atan2(y_cm, d))],
        })

    cam = Camera(size).start()
    jobs, wt = writer()
    meta = {"kind": "fixations", "size": size, "distance_cm": d, "window_rect": [rx, ry, rw, rh],
            "screen_pt": [sw, sh], "screen_cm": SCREEN_CM, "fixations": []}
    i, mode, frames, pts, t_rec = 0, "wait", [], [], 0.0
    while i < len(targets):
        tg = targets[i]
        img = np.zeros((rh, rw, 3), np.uint8)
        text(img, f"{i + 1}/{len(targets)}  space: fixated   r: redo last   esc: quit")
        bullseye(img, round(tg["fx"] * rw), round(tg["fy"] * rh), r, (0, 220, 0) if mode == "rec" else (255, 255, 255))
        cv2.imshow(WIN, img)
        k = cv2.waitKey(5)
        now = time.monotonic()
        if k == 27:
            break
        if mode == "wait" and k == ord(" "):
            mode, frames, pts, t_rec = "rec", [], [], now + 0.1
        if mode == "wait" and k == ord("r") and i > 0:
            i -= 1
            meta["fixations"].pop()
            continue
        while not cam.q.empty():
            t, f = cam.q.get()
            if mode == "rec" and t >= t_rec and len(frames) < 30:
                frames.append(f), pts.append(t)
        if mode == "rec" and len(frames) == 30:
            name = f"fix{i:02d}.npz"
            jobs.put((out / name, {"nv12": np.stack(frames), "pts": np.array(pts)}))
            meta["fixations"].append({**tg, "file": name, "t_press": t_rec - 0.1})
            mode, i = "wait", i + 1
    meta["camera"] = cam.state()
    cam.stop()
    jobs.put(None)
    wt.join()
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(out, meta["camera"])


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("formats")
    f.add_argument("--distance-cm", type=float, default=55)
    x = sub.add_parser("fixations")
    x.add_argument("--size", default="1920x1080")
    x.add_argument("--distance-cm", type=float, default=55)
    x.add_argument("--reps", type=int, default=1)
    a = p.parse_args()
    {"formats": run_formats, "fixations": run_fixations}[a.cmd](a)
