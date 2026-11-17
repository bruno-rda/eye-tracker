# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python-headless", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa", "pyobjc-framework-ApplicationServices"]
# ///
"""PROTOTYPE, throwaway. How long from a cursor call to the camera frame that shows it? (#23)

  uv run mirror.py             # the loop: a mirror faces the screen, the camera watches its own display
  uv run mirror.py trackpad    # how long the trackpad freezes after a cursor call; no mirror
  uv run mirror.py report      # re-analyse every file in results/

Loop: a white full-screen window; the cursor, a black block, is moved between grid positions at
stamped times, at random phase to the camera. Each position's patch in the camera image is found by
differencing; a frame's score at a position is its patch contrast, 0 with the cursor away, 1 with it
there. Loop latency is the stamp of the first frame whose score at the new position passes a
threshold, minus the stamp taken just before the call.
  conditions: {block96, block24, arrow} x warp, {block24, arrow} x event, interleaved; the smaller
  cursors are searched for only near where block96 was found
  event needs the Accessibility privilege for the terminal; without it the condition is skipped

Trackpad: keep a finger circling. The cursor is sent to the centre at random times; the freeze is
the time until it next leaves the centre.

Keys: space starts, esc quits and saves what there is. --fake paints a synthetic cursor into the
frames (a self-test of the code, no mirror). Summaries go to results/; no frames are kept.
"""

import argparse
import json
import os
import platform
import queue
import random
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SIZE = (1920, 1080)
GRID = [(x, y) for y in (0.2, 0.5, 0.8) for x in (0.14, 0.32, 0.5, 0.68, 0.86)]
BLOCKS = {"block96": 96, "block24": 24}
ALL = [("block96", "warp"), ("block96", "display_move"), ("block96", "event"), ("block24", "warp"), ("block24", "event"),
       ("arrow", "warp"), ("arrow", "event")]
CONDITIONS = [("block96", "warp"), ("block24", "warp"), ("arrow", "warp"), ("block24", "event"), ("arrow", "event")]
NEAR_PX = 50
ROUNDS, PER_ROUND = 3, 50
DWELL, PRE, POST = 0.4, (-0.12, -0.04), (0.25, 0.4)
THETAS = (0.1, 0.5, 0.9)
MIN_AREA, MIN_SEEN = 6, 4
SPACE, ESC = 49, 53
FAKE_DISPLAY_S, FAKE_EXPOSURE_S = 0.025, 0.008


def pct(a, q):
    return [round(float(v), 1) for v in np.percentile(a, q)] if len(a) else [None] * len(q)


# ---------------------------------------------------------------- analysis


def score(trial):
    """Per frame after the call: (stamp - call in s, score at the new position, score at the old)."""
    f = np.array(trial["frames"], float)
    if not len(f):
        return None
    t, ca, cb = f[:, 0], f[:, 2], f[:, 3]
    pre, post = (t >= PRE[0]) & (t < PRE[1]), (t >= POST[0]) & (t < POST[1])
    if pre.sum() < 2 or post.sum() < 2:
        return None
    a1, a0, b0, b1 = ca[pre].mean(), ca[post].mean(), cb[pre].mean(), cb[post].mean()
    if b1 - b0 < 0.5 * trial["c1b"] or a1 - a0 < 0.5 * trial["c1a"]:
        return None  # the cursor never showed at the new position, or was not at the old one
    keep = t >= PRE[1]
    return t[keep], ((cb - b0) / (b1 - b0))[keep], ((ca - a0) / (a1 - a0))[keep], float(np.std((cb[pre] - b0) / (b1 - b0)))


def analyse_loop(res):
    out = [f"{res['stamp']} loop{' (FAKE)' if res['meta'].get('fake') else ''}: macOS {res['meta']['macos']}, "
           f"{res['meta']['refresh_hz']:.0f} Hz, trusted {res['meta']['trusted']}, drops {res['meta'].get('drops')}"]
    for kind, cal in res["meta"]["calibration"].items():
        seen = [r for r in cal if r]
        out.append(f"  {kind}: {len(seen)} of {len(cal)} positions seen, patch area median "
                   f"{np.median([r['area'] for r in seen]) if seen else 0:.0f} px, contrast median "
                   f"{np.median([r['c1'] - r['c0'] for r in seen]) if seen else 0:.0f}, system cursor {res['meta']['cursor_pt'].get(kind)} pt")
    for note in res["meta"].get("notes", []):
        out.append(f"  note: {note}")
    frames = [f for t in res["trials"] for f in t["frames"]]
    if frames:
        f = np.array(frames, float)
        f[:, [0, 1, 5]] *= 1000
        out.append(f"  frame arrival in Python - stamp, ms: p5 {pct(f[:, 1] - f[:, 0], [5])[0]}  p50 {pct(f[:, 1] - f[:, 0], [50])[0]}  "
                   f"p95 {pct(f[:, 1] - f[:, 0], [95])[0]};  driver deliver - stamp p50 {pct(f[:, 5] - f[:, 0], [50])[0]};  "
                   f"exposure ms p50 {pct(f[:, 4], [50])[0]} (min {f[:, 4].min():.1f}, max {f[:, 4].max():.1f});  "
                   f"rolling shutter skew {res['meta'].get('skew_us')} us (driver metadata)")
    out.append("  loop latency = stamp of the first frame scoring >= theta at the new position - stamp before the call, ms")
    out.append(f"  {'condition':24} {'n':>4} {'lost':>4} | " + " | ".join(f"theta {th}: p5   p50   p95" for th in THETAS)
               + " | call ms p50 p95 | noise | partial | a+b | left at p95")
    for kind, call in ALL:
        T = [t for t in res["trials"] if t["kind"] == kind and t["call"] == call]
        if not T:
            continue
        lat, rows, first, sums, noise, steps, dur = {th: [] for th in THETAS}, [], [], [], [], [], []
        lost = 0
        for t in T:
            s = score(t)
            if s is None or not (s[1] >= THETAS[-1]).any():
                lost += 1
                continue
            ts, sb, sa, nz = s
            for th in THETAS:
                lat[th].append(1000 * ts[np.argmax(sb >= th)])
            i = int(np.argmax(sb >= THETAS[0]))
            first.append(sb[i])
            sums.append(sb[i] + sa[i])
            steps.append([sb[j] if j < len(sb) else np.nan for j in range(i - 1, i + 4)])
            rows.append(t["row_b"])
            noise.append(nz)
            dur.append(1000 * (t["t1"] - t["t0"]))
        wrong = sum(t.get("cursor_pt", res["meta"]["cursor_pt"][kind]) != res["meta"]["cursor_pt"][kind] for t in T)
        if wrong:
            out.append(f"  {kind} {call}: {wrong} trials read back a different system cursor")
        if not first:
            out.append(f"  {kind + ' ' + call:24} {len(T):4} {lost:4} | nothing detected")
            continue
        first, mid = np.array(first), np.array(lat[0.5])
        partial = (first < 0.9).mean()
        cells = " | ".join("        " + "".join(f"{v:6.1f}" for v in pct(lat[th], [5, 50, 95])) for th in THETAS)
        out.append(f"  {kind + ' ' + call:24} {len(T):4} {lost:4} | {cells} | {pct(dur, [50])[0]:7} {pct(dur, [95])[0]:5} | "
                   f"{np.median(noise):.3f} | {100 * partial:4.0f}%   | {np.mean(np.abs(np.array(sums)[first < 0.9] - 1)) if partial else 0:.2f} | "
                   f"{100 - pct(lat[0.5], [95])[0]:.1f}")
        st = np.nanmean(np.array(steps), axis=0)
        slope = np.polyfit(rows, mid, 1)[0] if np.ptp(rows) > 50 else float("nan")
        out.append(f"      score by frame from the one before detection: {' '.join(f'{v:.2f}' for v in st)};  first-frame score "
                   f"p5 p50 p95 {pct(first, [5, 50, 95])};  latency against image row {1080 * slope:.1f} ms per 1080 rows "
                   f"(rows {min(rows):.0f} to {max(rows):.0f})")
    out.append("  noise: SD of the score before the call. partial: first frames scoring under 0.9. a+b: mean |old + new - 1| in those.")
    out.append("  left at p95: 100 ms - p95 at theta 0.5, what the pipeline may spend from frame stamp to cursor call.")
    return "\n".join(out)


def freeze(trial):
    """Freeze: the call to the cursor's next move away from where the call put it."""
    c = np.array(trial["changes"], float)  # t - call, x, y at each change of the polled location
    tx, ty = trial["target"]
    at = np.flatnonzero((c[:, 0] >= -0.002) & (np.hypot(c[:, 1] - tx, c[:, 2] - ty) < 1.5))
    if not len(at):
        return None  # the call did not move the cursor
    i = at[0]
    before = c[c[:, 0] < 0][:, 0]
    gaps = np.diff(before) * 1000
    if len(gaps) < 5 or before[-1] < -0.06:
        return None  # the finger was not moving at the call
    if i + 1 >= len(c):
        return {"freeze": float("inf"), "gap": float(np.median(gaps)), "step": float("nan"), "step_before": float("nan")}
    pre = c[c[:, 0] < 0]
    return {"freeze": 1000 * c[i + 1, 0], "gap": float(np.median(gaps)), "gap95": float(np.percentile(gaps, 95)),
            "step": float(np.hypot(c[i + 1, 1] - tx, c[i + 1, 2] - ty)),
            "step_before": float(np.median(np.hypot(np.diff(pre[:, 1]), np.diff(pre[:, 2]))))}


def analyse_trackpad(res):
    out = [f"{res['stamp']} trackpad: macOS {res['meta']['macos']}, trusted {res['meta']['trusted']}, poll every "
           f"{res['meta'].get('poll_ms', float('nan')):.2f} ms",
           "  freeze = call to the cursor next leaving the point it was sent to, ms; gap = time between cursor moves before the call",
           f"  {'call':28} {'n':>3} {'used':>4} | freeze p5   p50   p95   max | gap p50  p95 | first step pt (before: per move)"]
    for name in res["meta"]["order"]:
        T = [t for t in res["trials"] if t["call"] == name]
        F = [f for f in map(freeze, T) if f]
        if not F:
            out.append(f"  {name:28} {len(T):3} {0:4} | the call did not move the cursor, or the finger was still")
            continue
        fr = [f["freeze"] for f in F]
        out.append(f"  {name:28} {len(T):3} {len(F):4} | " + "".join(f"{v:6.1f}" for v in pct(fr, [5, 50, 95])) + f"{max(fr):6.1f} | "
                   f"{np.median([f['gap'] for f in F]):6.1f} {np.median([f.get('gap95', np.nan) for f in F]):5.1f} | "
                   f"{np.nanmedian([f['step'] for f in F]):5.1f} ({np.nanmedian([f['step_before'] for f in F]):.1f})")
    return "\n".join(out)


def report():
    for p in sorted(RESULTS.glob("*.json")):
        res = json.loads(p.read_text())
        print((analyse_loop if res["mode"] == "loop" else analyse_trackpad)(res), "\n")


# ---------------------------------------------------------------- cursor, window


def location():
    p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return p.x, p.y


def make_calls():
    d = Quartz.CGMainDisplayID()
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    def event(p):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, p, 0))

    def associate(p):
        Quartz.CGWarpMouseCursorPosition(p)
        Quartz.CGAssociateMouseAndMouseCursorPosition(True)

    return {
        "warp": Quartz.CGWarpMouseCursorPosition,
        "display_move": lambda p: Quartz.CGDisplayMoveCursorToPoint(d, p),
        "event": event,
        "warp + associate": associate,
    }, src


class UI:
    cursor = None
    cursors = {}
    text = ""
    preview = None
    win = view = None


KEYS = queue.Queue()
QUIT = threading.Event()


def build_window():
    import AppKit

    class Win(AppKit.NSWindow):
        def canBecomeKeyWindow(self):
            return True

        def keyDown_(self, ev):
            if ev.keyCode() == ESC:
                if QUIT.is_set():
                    os._exit(1)
                QUIT.set()
                threading.Timer(4, os._exit, [1]).start()
            KEYS.put(ev.keyCode())

    class View(AppKit.NSView):
        def resetCursorRects(self):
            if UI.cursor is not None:
                self.addCursorRect_cursor_(self.bounds(), UI.cursor)

        def drawRect_(self, rect):
            b = self.bounds()
            AppKit.NSColor.whiteColor().set()
            AppKit.NSRectFill(b)
            if UI.preview is not None:
                UI.preview.drawInRect_((((b.size.width - 480) / 2, 16), (480, 270)))
            attrs = {AppKit.NSFontAttributeName: AppKit.NSFont.systemFontOfSize_(15),
                     AppKit.NSForegroundColorAttributeName: AppKit.NSColor.grayColor()}
            for i, line in enumerate(UI.text.split("\n")):
                AppKit.NSString.stringWithString_(line).drawAtPoint_withAttributes_((24, b.size.height - 44 - 22 * i), attrs)

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    for name, pt in BLOCKS.items():
        img = AppKit.NSImage.alloc().initWithSize_((pt, pt))
        img.lockFocus()
        AppKit.NSColor.blackColor().set()
        AppKit.NSRectFill(((0, 0), (pt, pt)))
        img.unlockFocus()
        UI.cursors[name] = AppKit.NSCursor.alloc().initWithImage_hotSpot_(img, (pt / 2, pt / 2))
    UI.cursors["arrow"] = AppKit.NSCursor.arrowCursor()
    frame = AppKit.NSScreen.mainScreen().frame()
    UI.win = Win.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
    UI.win.setLevel_(AppKit.NSMainMenuWindowLevel + 2)
    UI.view = View.alloc().initWithFrame_(frame)
    UI.win.setContentView_(UI.view)
    UI.win.makeKeyAndOrderFront_(None)
    app.setPresentationOptions_(AppKit.NSApplicationPresentationHideDock | AppKit.NSApplicationPresentationHideMenuBar)
    app.activateIgnoringOtherApps_(True)
    return frame.size.width, frame.size.height


def show(**kw):
    """Change text, preview (a PNG's bytes or None) or cursor, on the main thread."""
    import AppKit
    from PyObjCTools import AppHelper

    def apply():
        if "text" in kw:
            UI.text = kw["text"]
        if "preview" in kw:
            png = kw["preview"]
            UI.preview = png and AppKit.NSImage.alloc().initWithData_(AppKit.NSData.dataWithBytes_length_(png, len(png)))
        if "cursor" in kw:
            UI.cursor = UI.cursors[kw["cursor"]]
            UI.win.invalidateCursorRectsForView_(UI.view)
            UI.cursor.set()
        UI.view.setNeedsDisplay_(True)

    AppHelper.callAfter(apply)


def cursor_pt():
    import AppKit
    from PyObjCTools import AppHelper

    got = []
    AppHelper.callAfter(lambda: got.append(AppKit.NSCursor.currentSystemCursor().image().size()))
    for _ in range(100):
        if got:
            return [round(got[0].width), round(got[0].height)]
        time.sleep(0.01)


def key(code):
    hit = False
    while not KEYS.empty():
        hit |= KEYS.get() == code
    return hit


class Quit(Exception):
    pass


def nap(s):
    if QUIT.wait(s):
        raise Quit


# ---------------------------------------------------------------- the loop


class Grabber(threading.Thread):
    """Pulls frames; keeps the last few, and each frame's contrast at every patch while `rois` is set."""

    def __init__(self, cam, fake=None):
        super().__init__(daemon=True)
        self.cam, self.fake = cam, fake
        self.recent, self.records, self.rois, self.skew = deque(maxlen=10), [], None, None
        self.start()

    def run(self):
        while True:
            pts, arrival, meta, y = self.cam.q.get()
            if self.fake:
                y = self.fake.paint(pts, y)
            self.skew = meta.get("skew_us", self.skew)
            self.recent.append((pts, y))
            rois = self.rois
            if rois is not None:
                self.records.append((pts, arrival, 1000 * meta.get("exposure_s", 0), meta.get("deliver_s", float("nan")),
                                     [contrast(y, r) if r else 0.0 for r in rois]))

    def mean_after(self, t, n):
        while True:
            got = [y for pts, y in list(self.recent) if pts >= t]
            if len(got) >= n:
                return np.mean(got[:n], axis=0, dtype=np.float32)
            nap(0.01)


class Fake:
    """Self-test: a grey field with a dark block where the cursor was FAKE_DISPLAY_S ago, exposed for FAKE_EXPOSURE_S."""

    def __init__(self):
        self.hist, self.kind = [(0.0, (0.0, 0.0))], "block96"
        self.noise = [np.random.normal(200, 2, (SIZE[1], SIZE[0])).astype(np.uint8) for _ in range(4)]
        self.i = 0

    def paint(self, pts, y):
        self.i += 1
        y = self.noise[self.i % 4].copy()
        half = {"block96": 22, "block24": 6, "arrow": 4}[self.kind]
        lo, hi = pts - FAKE_DISPLAY_S, pts - FAKE_DISPLAY_S + FAKE_EXPOSURE_S
        hist = self.hist[-6:] + [(float("inf"), None)]
        for (t, p), (t_next, _) in zip(hist, hist[1:]):
            w = (min(hi, t_next) - max(lo, t)) / FAKE_EXPOSURE_S
            if w > 0:
                cx, cy = int(1700 - 0.9 * p[0]), int(100 + 0.9 * p[1])
                sl = (slice(cy - half, cy + half), slice(cx - half, cx + half))
                y[sl] = (y[sl] * (1 - 0.9 * w)).astype(np.uint8)
        return y


def contrast(y, r):
    c = y[r["sl"]]
    return float(c[r["ring"]].mean()) - float(c[r["mask"]].mean())


def find_patches(imgs, near=None):
    """One patch per position: where its image is darker than the median of them all."""
    import cv2

    bg = np.median(np.stack(imgs), axis=0)
    rois = []
    for i, img in enumerate(imgs):
        d = bg - img
        thr = max(8.0, 6 * 1.4826 * float(np.median(np.abs(d[::4, ::4]))))
        m = (d > thr).astype(np.uint8)
        if near is not None:
            if near[i] is None:
                rois.append(None)
                continue
            x, y = (int(v) for v in near[i]["xy"])
            keep = np.zeros_like(m)
            keep[max(0, y - NEAR_PX):y + NEAR_PX, max(0, x - NEAR_PX):x + NEAR_PX] = 1
            m &= keep
        n, lab, stats, cent = cv2.connectedComponentsWithStats(m, connectivity=8)
        if n < 2:
            rois.append(None)
            continue
        j = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        area = int(stats[j, cv2.CC_STAT_AREA])
        if area < MIN_AREA or area < 0.5 * m.sum():
            rois.append(None)
            continue
        x, y, w, h = (int(v) for v in stats[j, :4])
        sl = (slice(max(0, y - 10), y + h + 10), slice(max(0, x - 10), x + w + 10))
        mask = lab[sl] == j
        ring = ~cv2.dilate(mask.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        r = {"sl": sl, "mask": mask, "ring": ring, "xy": [float(cent[j][0]), float(cent[j][1])], "area": area}
        r["c1"], r["c0"] = contrast(img, r), contrast(bg, r)
        rois.append(r)
    return rois


def run_loop(args, W, H):
    import cv2
    import capture

    calls, _ = make_calls()
    fake = Fake() if args.fake else None
    if fake:
        for name, f in list(calls.items()):
            calls[name] = lambda p, f=f: (fake.hist.append((time.monotonic(), p)), f(p))[1]
    points = [(round(x * W), round(y * H)) for x, y in GRID]
    trusted = bool(Quartz.CGPreflightPostEventAccess())
    cam = capture.Camera(SIZE).start()
    grab = Grabber(cam, fake)
    res = {"mode": "loop", "stamp": datetime.now().strftime("%Y%m%d-%H%M%S"), "trials": [],
           "meta": {"macos": platform.mac_ver()[0], "screen_pt": [W, H], "points": points, "trusted": trusted, "fake": args.fake,
                    "refresh_hz": Quartz.CGDisplayModeGetRefreshRate(Quartz.CGDisplayCopyDisplayMode(Quartz.CGMainDisplayID())),
                    "calibration": {}, "cursor_pt": {}, "notes": []}}
    home = location()

    def sweep(kind, settle, n, preview=False):
        if fake:
            fake.kind = kind
        imgs = []
        for p in points:
            calls["warp"](p)
            imgs.append(grab.mean_after(time.monotonic() + settle, n))
            if preview:
                show(preview=png(grab.recent[-1][1], preview))
        return imgs

    def png(y, rois):
        small = cv2.cvtColor(cv2.resize(y, (480, 270), interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2BGR)
        for r in rois:
            if r:
                cv2.circle(small, (int(r["xy"][0] / 4), int(r["xy"][1] / 4)), 6, (0, 160, 0), 2)
        return cv2.imencode(".png", small)[1].tobytes()

    try:
        show(cursor="block96", text="Mirror loop. Starting the camera.")
        nap(1.5)
        rois = [None] * len(points)
        while True:  # setup: aim the mirror
            rois_new = find_patches(sweep("block96", 0.12, 2, preview=rois))
            rois[:] = rois_new
            seen = sum(r is not None for r in rois)
            show(text=f"Mirror loop. Face a mirror at the screen until the camera sees the display (preview below, circles mark the cursor patches found).\n"
                      f"Positions seen: {seen} of {len(points)} (at least {MIN_SEEN}).\n"
                      f"space: start, about {ROUNDS * PER_ROUND * len(CONDITIONS) * (DWELL + 0.05) / 60 + 1:.0f} min, hands off and out of the mirror.   esc: quit.")
            if (key(SPACE) or args.auto) and seen >= MIN_SEEN:
                break
        show(preview=None, text="Calibrating.")
        nap(1.5)
        cal = {}
        for kind in dict.fromkeys(["block96"] + [k for k, _ in CONDITIONS]):
            show(cursor=kind)
            nap(0.5)
            res["meta"]["cursor_pt"][kind] = cursor_pt()
            cal[kind] = find_patches(sweep(kind, 0.15, 4), None if kind == "block96" else cal["block96"])
            res["meta"]["calibration"][kind] = [r and {k: r[k] for k in ("xy", "area", "c0", "c1")} for r in cal[kind]]
        conds = []
        for kind, call in CONDITIONS:
            if sum(r is not None for r in cal[kind]) < 2:
                res["meta"]["notes"].append(f"{kind} {call} skipped: the cursor was found at fewer than 2 positions")
            elif call == "event" and not trusted:
                res["meta"]["notes"].append("event skipped: the terminal lacks the Accessibility privilege")
            else:
                conds.append((kind, call))
        per = args.auto or PER_ROUND
        for rnd in range(1 if args.auto else ROUNDS):
            for kind, call in random.sample(conds, len(conds)):
                show(cursor=kind, text=f"round {rnd + 1} of {ROUNDS}: {kind} {call}")
                if fake:
                    fake.kind = kind
                ok = [k for k, r in enumerate(cal[kind]) if r]
                a = random.choice(ok)
                calls["warp"](points[a])
                grab.records, grab.rois = [], cal[kind]
                nap(0.5)
                pt = cursor_pt()
                block = []
                for _ in range(per):
                    b = random.choice([k for k in ok if k != a])
                    nap(random.uniform(0, 2 / 30))
                    t0 = time.monotonic()
                    calls[call](points[b])
                    t1 = time.monotonic()
                    at = location()
                    nap(DWELL)
                    block.append({"kind": kind, "call": call, "round": rnd, "cursor_pt": pt, "a": a, "b": b, "t0": t0, "t1": t1,
                                  "moved": abs(at[0] - points[b][0]) < 1.5 and abs(at[1] - points[b][1]) < 1.5,
                                  "row_a": cal[kind][a]["xy"][1], "row_b": cal[kind][b]["xy"][1],
                                  "c1a": cal[kind][a]["c1"] - cal[kind][a]["c0"], "c1b": cal[kind][b]["c1"] - cal[kind][b]["c0"]})
                    a = b
                nap(0.3)
                grab.rois, records = None, grab.records
                for t in block:
                    t["frames"] = [[round(pts - t["t0"], 5), round(arr - t["t0"], 5), round(c[t["a"]], 2), round(c[t["b"]], 2),
                                    round(exp, 3), round(dl - t["t0"], 5)]
                                   for pts, arr, exp, dl, c in records if PRE[0] <= pts - t["t0"] < POST[1]]
                res["trials"] += block
    except Quit:
        res["meta"]["notes"].append("quit early")
    finally:
        calls["warp"](home)
        res["meta"]["drops"], res["meta"]["skew_us"] = cam.sink.drops, grab.skew
        cam.stop()
        finish(res)


# ---------------------------------------------------------------- the trackpad


def run_trackpad(args, W, H):
    calls, src = make_calls()
    trusted = bool(Quartz.CGPreflightPostEventAccess())
    order = ["warp", "warp + associate", "display_move"] + (["event"] if trusted else [])
    res = {"mode": "trackpad", "stamp": datetime.now().strftime("%Y%m%d-%H%M%S"), "trials": [],
           "meta": {"macos": platform.mac_ver()[0], "screen_pt": [W, H], "trusted": trusted, "order": order + ["warp, suppression 0"],
                    "suppression_s": Quartz.CGEventSourceGetLocalEventsSuppressionInterval(src)}}
    polls, stop = deque(maxlen=20000), threading.Event()

    def poll():
        while not stop.is_set():
            polls.append((time.monotonic(), *location()))
            time.sleep(0.0005)

    threading.Thread(target=poll, daemon=True).start()
    centre = (W / 2, H / 2)
    n = args.auto or 15

    def trial(name, call):
        nap(random.uniform(1.0, 1.6))
        while not args.auto:  # wait for a moving finger
            p = list(polls)[-120:]
            if any(q[1:] != p[-1][1:] for q in p if q[0] > p[-1][0] - 0.05):
                break
            nap(0.02)
        x, y = location()
        target = centre if abs(x - centre[0]) + abs(y - centre[1]) > 150 else (centre[0] + 250, centre[1])
        t0 = time.monotonic()
        call(target)
        t1 = time.monotonic()
        nap(0.8)
        p = [q for q in list(polls) if t0 - 0.3 <= q[0] <= t0 + 0.8]
        changes = [[round(q[0] - t0, 5), q[1], q[2]] for i, q in enumerate(p) if i == 0 or q[1:] != p[i - 1][1:]]
        res["trials"].append({"call": name, "t0": t0, "t1": t1, "target": target, "changes": changes})

    try:
        show(cursor="arrow", text="Trackpad freeze. Keep one finger circling on the trackpad, steadily, until this says done.\n"
                                  "The cursor is sent to the centre now and then; keep circling.\nspace: start.   esc: quit.")
        while not (key(SPACE) or args.auto):
            nap(0.05)
        todo = [name for name in order for _ in range(n)]
        random.shuffle(todo)
        for i, name in enumerate(todo):
            show(text=f"Keep circling. {i + 1} of {len(todo) + n}")
            trial(name, calls[name])
        Quartz.CGEventSourceSetLocalEventsSuppressionInterval(src, 0.0)
        res["meta"]["suppression_set_s"] = Quartz.CGEventSourceGetLocalEventsSuppressionInterval(src)
        for i in range(n):
            show(text=f"Keep circling. {len(todo) + i + 1} of {len(todo) + n}")
            trial("warp, suppression 0", calls["warp"])
    except Quit:
        res["meta"]["notes"] = ["quit early"]
    finally:
        stop.set()
        Quartz.CGEventSourceSetLocalEventsSuppressionInterval(src, res["meta"]["suppression_s"])
        t = np.array([q[0] for q in polls])
        res["meta"]["poll_ms"] = float(np.median(np.diff(t)) * 1000) if len(t) > 1 else float("nan")
        finish(res)


def finish(res):
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{res['stamp']}-{res['mode']}{'-fake' if res['meta'].get('fake') else ''}.json"
    path.write_text(json.dumps(res))
    try:
        print((analyse_loop if res["mode"] == "loop" else analyse_trackpad)(res))
    except Exception as e:
        print("analysis failed:", repr(e))
    print(path, flush=True)
    os._exit(0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="loop", choices=["loop", "trackpad", "report"])
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--auto", type=int, default=0, help="self-test: start without the key, this many calls per block")
    args = ap.parse_args()
    if args.mode == "report":
        report()
        sys.exit()
    import Quartz
    from PyObjCTools import AppHelper

    sys.path.insert(0, str(HERE))
    if args.auto:
        threading.Timer(120, os._exit, [2]).start()
    W, H = build_window()

    def guarded(run):
        try:
            run(args, W, H)
        except BaseException:
            import traceback

            traceback.print_exc()
            os._exit(1)

    threading.Thread(target=guarded, args=(run_trackpad if args.mode == "trackpad" else run_loop,), daemon=True).start()
    AppHelper.runEventLoop()
