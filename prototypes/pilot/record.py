# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""PROTOTYPE, throwaway. Records one whole pilot session to size the evaluation protocol (#15).

  uv run record.py --quick             # rehearsal: the same flow in about a minute
  uv run record.py --light daylight    # the session, about 20 min; have a tape measure
  uv run record.py --head-only         # 9 pool fixations and the head block, about 2 min

Blocks, each opened by typing the measured eye-to-screen distance:
  pool   25 fixation targets on a 5 x 5 grid, then a 30 s pursuit lap
  early  45 fixation targets
  gap    10 min of ordinary laptop use: the window closes, the camera keeps recording, three beeps end it
  late   45 fixation targets
  head   10 fixation targets, each held 4 s while the head moves as if nudging the cursor

A fixation: look at the centre of the bullseye, press space, keep looking until it stops being green.
r redoes the previous target, esc ends the session early (what was recorded is kept).

Every camera frame goes to recordings/pilot/<session>/frames.mkv (x264 lossless), its timestamp and
CRC to frames.csv; fixation targets, key-press times, cursor positions and clicks to events.jsonl on
the same clock. No key identities, no screen content.
"""

import argparse
import json
import math
import random
import subprocess
import threading
import time
import zlib
from datetime import datetime
from pathlib import Path

import AppKit
import cv2
import Foundation
import numpy as np
import Quartz

from capture import Camera

ROOT = Path(__file__).resolve().parents[2] / "recordings" / "pilot"
SCREEN_CM = (30.24, 19.64)  # 3024 x 1964 px at 254 ppi (Apple tech specs, MacBook Pro 14-inch)
SIZE = (1920, 1080)
WIN = "pilot"
WHITE, GREEN, GREY = (255, 255, 255), (0, 220, 0), (130, 130, 130)
SPACE, ESC, ENTER, BACK = 32, 27, 13, 127
WINDOW_S = 31 / 30  # 30 retained frames after the press
HEAD_S = 4.0
MARGIN = 24  # points from a fixation target's centre to the window edge

INTRO = {
    "pool": ["Calibration pool: {n} fixation targets."],
    "early": ["Test block: {n} fixation targets."],
    "late": ["Test block: {n} fixation targets."],
    "head": ["Head block: {n} fixation targets.",
             "After space, keep your eyes on the bullseye for 4 s while moving your head",
             "small and slow: left, right, up, down, the nose travelling about 1 cm."],
}
HOW = ["Look at the centre of the bullseye, press space, keep looking while it is green.",
       "Move as you naturally would. r redoes the previous target, esc ends the session."]


class Quit(Exception):
    pass


class Events:
    """One JSON line per event, stamped on the camera's clock."""

    def __init__(self, path):
        self.f, self.lock = path.open("w"), threading.Lock()

    def __call__(self, kind, **kw):
        t = time.monotonic()
        with self.lock:
            self.f.write(json.dumps({"t": t, "kind": kind, **kw}) + "\n")
            self.f.flush()
        return t


class Recorder(threading.Thread):
    """Drains the camera queue into ffmpeg. One line per frame: pts, crc32, time written."""

    def __init__(self, cam, out):
        super().__init__()
        self.cam, self.n, self.last, self.backlog, self.misfits = cam, 0, 0.0, 0, 0
        self.ff = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "nv12", "-s", "%dx%d" % SIZE,
             "-framerate", "30", "-i", "-", "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
             "-pix_fmt", "yuv420p", str(out / "frames.mkv")],
            stdin=subprocess.PIPE)
        self.log = (out / "frames.csv").open("w")

    def run(self):
        while (item := self.cam.q.get()) is not None:
            t, nv12 = item
            if nv12.shape != (SIZE[1] * 3 // 2, SIZE[0]):  # frames before the format is set
                self.misfits += 1
                continue
            self.ff.stdin.write(nv12.data)
            self.log.write(f"{t!r},{zlib.crc32(nv12.data)},{time.monotonic()!r}\n")
            self.log.flush()
            self.n, self.last = self.n + 1, t
            self.backlog = max(self.backlog, self.cam.q.qsize())

    def close(self):
        self.cam.stop()
        self.cam.q.put(None)
        self.join()
        self.ff.stdin.close()
        self.log.close()
        return self.ff.wait()


def poll_input(ev, stop):
    """Cursor positions, clicks and key-press times from event counters: no permission, no key identities."""
    state = Quartz.kCGEventSourceStateCombinedSessionState
    kinds = {"key": Quartz.kCGEventKeyDown, "click": Quartz.kCGEventLeftMouseDown, "right_click": Quartz.kCGEventRightMouseDown}
    count = lambda: {k: Quartz.CGEventSourceCounterForEventType(state, v) for k, v in kinds.items()}
    last, pos = count(), None
    while not stop.wait(0.01):
        p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        p = (round(p.x, 1), round(p.y, 1))
        if p != pos:
            ev("cursor", x=p[0], y=p[1])
            pos = p
        now = count()
        for k in kinds:
            for _ in range(now[k] - last[k]):
                ev(k) if k == "key" else ev(k, x=p[0], y=p[1])
        last = now


class UI:
    def __init__(self, ev, auto):
        self.ev, self.auto = ev, auto
        self.screen_pt = tuple(AppKit.NSScreen.mainScreen().frame().size)
        self.k = SCREEN_CM[0] / self.screen_pt[0]  # cm per point
        self.open()

    def open(self):
        """Fullscreen; the content rect in points, top-left origin. Below the notch strip on this machine."""
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        for _ in range(100):  # let the fullscreen transition settle
            cv2.imshow(WIN, np.zeros((10, 10, 3), np.uint8))
            cv2.waitKey(20)
        AppKit.NSApp().activateIgnoringOtherApps_(True)
        f = max((w.frame() for w in AppKit.NSApp().windows()), key=lambda f: f.size.width * f.size.height)
        self.rect = int(f.origin.x), int(self.screen_pt[1] - f.origin.y - f.size.height), int(f.size.width), int(f.size.height)
        self.ev("window", rect=self.rect)

    def close(self):
        cv2.destroyAllWindows()
        for _ in range(20):
            cv2.waitKey(10)

    def cm(self, x, y):
        """Window points to centimetres from the screen centre, x right, y down."""
        return {"x_cm": (self.rect[0] + x) * self.k - SCREEN_CM[0] / 2, "y_cm": (self.rect[1] + y) * self.k - SCREEN_CM[1] / 2}

    def radius(self, distance_cm):
        return max(4, round(math.tan(math.radians(0.3)) * distance_cm / self.k))  # 0.6 deg fixation target

    def show(self, lines=(), target=None, colour=WHITE, r=14, hud=""):
        _, _, w, h = self.rect
        img = np.zeros((h, w, 3), np.uint8)
        if target:
            x, y = target
            cv2.circle(img, (x, y), r, colour, -1, cv2.LINE_AA)
            cv2.line(img, (x - r, y), (x + r, y), (0, 0, 0), max(1, r // 6), cv2.LINE_AA)
            cv2.line(img, (x, y - r), (x, y + r), (0, 0, 0), max(1, r // 6), cv2.LINE_AA)
            cv2.circle(img, (x, y), max(2, r // 4), colour, -1, cv2.LINE_AA)
            if hud:  # away from the fixation target
                cv2.putText(img, hud, (w // 2 - 40, 30 if y > h // 2 else h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (70, 70, 70), 1, cv2.LINE_AA)
        for j, s in enumerate(lines):
            tw = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0][0]
            cv2.putText(img, s, ((w - tw) // 2, h // 2 - 20 * len(lines) + 40 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GREY, 2, cv2.LINE_AA)
        cv2.imshow(WIN, img)
        k = cv2.waitKey(5) & 0xFF
        if k == ESC:
            raise Quit
        return k

    def distance(self, block, n):
        """The block's intro; returns the typed viewing distance."""
        self.ev("prompt", block=block)
        lines = [s.format(n=n) for s in INTRO[block]] + HOW + ["", "Sit as you would to work and tape-measure eye to screen."]
        s, t0 = "", time.monotonic()
        while True:
            k = self.show(lines + [f"Distance in cm, then enter: {s}_"])
            if self.auto and time.monotonic() - t0 > 0.5:
                return 55.0
            if chr(k) in "0123456789.":
                s += chr(k)
            elif k == BACK:
                s = s[:-1]
            elif k in (ENTER, 3) and s.replace(".", "", 1).isdigit():
                return float(s)


def grid(nx, ny, w, h, rng=None):
    """(cell, x, y) per cell in window points: on a lattice reaching the edges, or random inside each cell."""
    out = []
    for j in range(ny):
        for i in range(nx):
            if rng:
                x = rng.uniform(max(MARGIN, i * w / nx), min(w - MARGIN, (i + 1) * w / nx))
                y = rng.uniform(max(MARGIN, j * h / ny), min(h - MARGIN, (j + 1) * h / ny))
            else:
                x, y = MARGIN + i * (w - 2 * MARGIN) / (nx - 1), MARGIN + j * (h - 2 * MARGIN) / (ny - 1)
            out.append(([i, j], round(x), round(y)))
    return out


def fixate(ui, rec, block, i, n, cell, x, y, r, hold_s):
    """One self-paced fixation; False when the previous one is to be redone."""
    t_on, t_press = ui.ev("target_on", block=block, i=i, cell=cell, **ui.cm(x, y)), None
    while True:
        k = ui.show(target=(x, y), colour=GREEN if t_press else WHITE, r=r, hud=f"{i + 1}/{n}")
        now = time.monotonic()
        if t_press is None:
            if k == SPACE or (ui.auto and now - t_on > 0.4):
                t_press = ui.ev("press", block=block, i=i)
            elif k == ord("r") and i > 0:
                ui.ev("redo", block=block, i=i - 1)
                return False
        elif rec.last >= t_press + hold_s or now > t_press + hold_s + 0.5:
            ui.ev("target_off", block=block, i=i)
            return True


def run_block(ui, rec, block, targets, hold_s=WINDOW_S, then=None):
    d = ui.distance(block, len(targets))
    ui.ev("block_start", block=block, distance_cm=d)
    r, i = ui.radius(d), 0
    while i < len(targets):
        i += 1 if fixate(ui, rec, block, i, len(targets), *targets[i], r, hold_s) else -1
    if then:
        then(r)
    ui.ev("block_end", block=block)


def pursuit(ui, seconds, r):
    """One clockwise lap of the window's inset rectangle at constant speed."""
    _, _, w, h = ui.rect
    c = [(MARGIN, MARGIN), (w - MARGIN, MARGIN), (w - MARGIN, h - MARGIN), (MARGIN, h - MARGIN), (MARGIN, MARGIN)]
    leg = [math.dist(c[i], c[i + 1]) for i in range(4)]

    def at(u):
        d = u * sum(leg)
        for i in range(4):
            if d <= leg[i]:
                return [round(a + (b - a) * d / leg[i]) for a, b in zip(c[i], c[i + 1])]
            d -= leg[i]
        return list(c[0])

    t0 = time.monotonic()
    while ui.show(["Follow the moving bullseye with your eyes. Space starts."], target=c[0], r=r) != SPACE:
        if ui.auto and time.monotonic() - t0 > 0.5:
            break
    t0 = ui.ev("pursuit_start", seconds=seconds)
    while (u := (time.monotonic() - t0) / seconds) < 1:
        x, y = at(u)
        ui.show(target=(x, y), r=r)
        ui.ev("pursuit", **ui.cm(x, y))
    ui.ev("pursuit_end")


def gap(ui, rec, seconds):
    ui.ev("gap_start")
    ui.close()
    t0 = time.monotonic()
    while (left := seconds - (time.monotonic() - t0)) > 0:
        print(f"\rgap: use the laptop as usual, {left / 60:4.1f} min left, {rec.n} frames, {rec.cam.sink.drops} drops ", end="", flush=True)
        cv2.waitKey(1)
        time.sleep(0.5)
    print()
    for _ in range(3):
        AppKit.NSBeep()
        time.sleep(0.4)
    ui.open()
    ui.ev("gap_end")


def main(a):
    out = ROOT / f"{datetime.now():%Y%m%d-%H%M%S}{'-quick' if a.quick else ''}{'-head' if a.head_only else ''}"
    out.mkdir(parents=True)
    n = dict(pool=(3, 2), test=(3, 2), head=(2, 1), pursuit=5, gap=20) if a.quick else \
        dict(pool=(5, 5), test=(9, 5), head=(5, 2), pursuit=30, gap=a.gap_min * 60)
    if a.head_only:
        n["pool"] = (3, 3)
    awake = Foundation.NSProcessInfo.processInfo().beginActivityWithOptions_reason_(  # no App Nap during the gap
        Foundation.NSActivityUserInitiated | Foundation.NSActivityLatencyCritical | Foundation.NSActivityIdleDisplaySleepDisabled, "recording")
    rng = random.Random(a.seed)
    ev = Events(out / "events.jsonl")
    ui = UI(ev, a.auto)
    meta = {"kind": "pilot", "started": datetime.now().isoformat(timespec="seconds"), "size": SIZE, "screen_pt": ui.screen_pt,
            "screen_cm": SCREEN_CM, "seed": a.seed, "light": a.light, "note": a.note, "sizes": n,
            "retained_frames": 30, "head_s": HEAD_S, "encoder": "libx264 ultrafast qp 0"}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    cam = Camera(SIZE).start()
    rec = Recorder(cam, out)
    rec.start()
    stop = threading.Event()
    poller = threading.Thread(target=poll_input, args=(ev, stop))
    poller.start()
    _, _, w, h = ui.rect
    shuffled = lambda t: rng.sample(t, len(t))
    try:
        run_block(ui, rec, "pool", shuffled(grid(*n["pool"], w, h)), then=None if a.head_only else lambda r: pursuit(ui, n["pursuit"], r))
        if not a.head_only:
            run_block(ui, rec, "early", shuffled(grid(*n["test"], w, h, rng)))
            gap(ui, rec, n["gap"])
            run_block(ui, rec, "late", shuffled(grid(*n["test"], w, h, rng)))
        run_block(ui, rec, "head", shuffled(grid(*n["head"], w, h, rng)), hold_s=HEAD_S)
    except Quit:
        ev("quit")
    finally:
        ev("end")
        stop.set()
        poller.join()
        meta["camera"] = cam.state()
        code = rec.close()
        ui.close()
        Foundation.NSProcessInfo.processInfo().endActivity_(awake)
        gb = (out / "frames.mkv").stat().st_size / 1e9
        meta |= {"frames": rec.n, "misfit_frames": rec.misfits, "backlog_max": rec.backlog, "ffmpeg_exit": code, "gb": round(gb, 3)}
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"{out}\n{rec.n} frames, {meta['camera']['drops']} drops, {gb:.2f} GB, {gb / max(rec.n, 1) * 1800:.2f} GB/min")
        print(f"next: uv run replay.py {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quick", action="store_true", help="tiny blocks and a 20 s gap, to rehearse")
    p.add_argument("--auto", action="store_true", help="presses its own keys (smoke test)")
    p.add_argument("--head-only", action="store_true", help="a 3 x 3 pool and the head block only")
    p.add_argument("--gap-min", type=float, default=10)
    p.add_argument("--seed", type=int, default=random.randrange(10**6))
    p.add_argument("--light", default="", help="daylight or lamp")
    p.add_argument("--note", default="", help="seating, anything unusual")
    main(p.parse_args())
