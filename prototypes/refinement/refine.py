# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "mediapipe==1.2.2", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""PROTOTYPE, throwaway. Does head movement land the cursor on a 24 pt hit target within 2 s? (#21)

  uv run refine.py --distance-cm 55     # tape-measure eye to screen first
  uv run refine.py --report             # one line per scored block and hold test so far

Real: the webcam, the landmarks, the head-to-cursor gain, the system cursor, the space bar.
Simulated: the jump. A hit target appears and, --jump-ms later (a stand-in for reaction, saccade and
latency), the cursor is placed at an offset from its centre, in a random direction:
  req   drawn per attempt, lognormal, median 1.5 deg, p90 3 deg (the estimator requirement)
  1.0, 0.5, 0   fixed; 0 is the control, the jump lands on the centre

It opens in free play: the head moves the cursor and the keys on screen tune the controller.
  p  practice: attempts with the settings on screen, unscored, until esc
  b  scored block: 45 attempts, one per cell of a 9 x 5 grid, then a summary
  h  hold test: 10 s head still, 10 s of small gaze shifts, 10 s of large ones; how far the cursor strays
Attempt rules (#14): look at the hit target, bring the cursor onto it with the head, press space.
The first press ends the attempt; a landing counts only within 2 s of the hit target appearing;
it stays 5 s at most; the next appears 1 to 2 s after the press; touching the trackpad is a miss.

Controller: the facial feature's image position, One Euro filtered, moves the cursor by
gain(speed) x displacement each frame; the gain rises smoothly from g_lo below v_lo to g_hi above
v_hi. Rest rule: after a jump the head is ignored for rest_min_ms, then until the feature has
stayed below rest_speed for rest_frames frames, so the gaze shift's own head movement does not
drag the cursor.

Summaries go to results/, landmark traces (no video) to recordings/refinement/<session>/.
"""

import argparse
import json
import math
import random
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1] / "recordings"
SCREEN_CM = (30.24, 19.64)  # 3024 x 1964 px at 254 ppi (Apple tech specs, MacBook Pro 14-inch)
SIZE = (1920, 1080)
WIN = "refinement"
FEATURES = {"tip": [4], "bridge": [168], "eyes": [33, 133, 362, 263], "rigid": [33, 133, 362, 263, 168, 4]}
NAMES = list(FEATURES)
OFFSETS = ["req", "1.0", "0.5", "0"]
SIGMA = math.log(2) / 1.2816  # lognormal with median 1.5 and p90 3
HALF = 12  # the hit target is a 24 pt square
LIMIT_S, CAP_S, N_STEADY = 2.0, 5.0, 10
WHITE, GREY, DIM = (255, 255, 255), (150, 150, 150), (70, 70, 70)
SPACE, ESC = 32, 27
URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"


@dataclass
class Params:
    feature: str = "tip"
    g_lo: float = 1.5  # points of cursor per pixel of feature, head slow
    g_hi: float = 6.0  # head fast
    v_lo: float = 8.0  # px/s
    v_hi: float = 60.0
    y_scale: float = 1.0  # vertical gain over horizontal
    mincut: float = 2.0  # One Euro filter: cutoff at rest, Hz
    beta: float = 0.1  # and its rise per px/s
    rest: bool = True
    rest_min_ms: float = 300.0  # the head's own movement starts up to about 0.26 s after a jump at 0.4 s (pilot, p90)
    rest_speed: float = 12.0  # px/s
    rest_frames: int = 3
    jump_ms: float = 400.0
    offset: str = "req"


class OneEuro:
    """Speed-adaptive low-pass (Casiez et al., CHI 2012)."""

    def __init__(self):
        self.x = None

    def __call__(self, x, dt, mincut, beta):
        if self.x is None:
            self.x, self.dx = x, np.zeros(2)
            return x
        a = lambda cut: 1 / (1 + 1 / (2 * math.pi * cut * dt))
        self.dx = self.dx + a(1.0) * ((x - self.x) / dt - self.dx)
        self.x = self.x + a(mincut + beta * float(np.linalg.norm(self.dx))) * (x - self.x)
        return self.x


class Controller:
    """Feature positions in, cursor positions out. Pure: the hold test replays it on every feature."""

    def __init__(self, cursor, bounds):
        self.c, self.bounds = np.array(cursor, float), bounds
        self.filt, self.prev, self.t = OneEuro(), None, None
        self.speed = self.gain = 0.0
        self.still, self.waiting, self.until = 0, False, 0.0

    def jump(self, to, p):
        self.c = np.array(to, float)
        self.waiting, self.until = p.rest, (self.t or 0) + p.rest_min_ms / 1000

    def step(self, t, f, p):
        if np.isnan(f[0]):  # face lost: the cursor holds
            self.filt, self.prev, self.t = OneEuro(), None, None
            return self.c
        dt = min(max(t - self.t, 1e-3), 0.2) if self.t else 1 / 30
        self.t = t
        s = self.filt(f, dt, p.mincut, p.beta)
        if self.prev is None:
            self.prev = s
            return self.c
        d, self.prev = s - self.prev, s
        self.speed = v = float(np.linalg.norm(d)) / dt
        self.still = self.still + 1 if v < p.rest_speed else 0
        if self.waiting and t >= self.until and self.still >= p.rest_frames:
            self.waiting = False
        u = min(max((v - p.v_lo) / max(p.v_hi - p.v_lo, 1e-6), 0), 1)
        self.gain = p.g_lo + (p.g_hi - p.g_lo) * u * u * (3 - 2 * u)
        if not self.waiting:  # the camera image is not mirrored: the user's right is its left
            x0, y0, x1, y1 = self.bounds
            self.c = np.clip(self.c + self.gain * d * (-1, p.y_scale), (x0, y0), (x1, y1))
        return self.c


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    c = (k / n + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(k / n * (1 - k / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 3), round(c + h, 3)]


def q(x, *ps):
    x = [v for v in x if v is not None]
    return [round(float(v), 2) for v in np.percentile(x, ps)] if x else [None] * len(ps)


def summarise(A, lat_ms):
    """The landing rate within 2 s, against time, starting offset and distance from the previous hit target."""
    def rate(xs, ok=lambda a: a["landed"] and a["press_s"] <= LIMIT_S):
        k = sum(map(ok, xs))
        return {"n": len(xs), "landed": k, "rate": round(k / len(xs), 3) if xs else None, "ci95": wilson(k, len(xs))}

    def binned(key, edges):
        return {f"{lo}-{hi}": rate([a for a in A if lo <= a[key] < hi]) | {"press_s_p50": q([a["press_s"] for a in A if lo <= a[key] < hi], 50)[0]}
                for lo, hi in zip(edges, edges[1:])}

    pressed = [a for a in A if a["press_s"] is not None]
    misses = [a for a in pressed if not a["landed"]]
    return {
        "attempts": len(A),
        "landed_within_2s": rate(A),
        "landed_any_time": rate(A, lambda a: a["landed"]),
        "no_press_in_5s": sum(a["press_s"] is None for a in A),
        "pressed_before_jump": sum(a["press_s"] is not None and a["refine_s"] is None for a in A),
        "trackpad": sum(a["trackpad"] for a in A),
        "press_s_p50_p90": q([a["press_s"] for a in A], 50, 90),
        "refine_s_p50_p90": q([a["refine_s"] for a in A], 50, 90),  # jump to press
        "rest_s_p50_p90": q([a["rest_s"] for a in A], 50, 90),  # jump to the head at rest
        "pressed_before_rest": sum(a["rest_s"] is None and a["refine_s"] is not None for a in A),  # the head never came in; all of them when the rule is off
        "landed_by_press_s": {str(t): rate(A, lambda a: a["landed"] and a["press_s"] <= t)["rate"] for t in (1, 1.25, 1.5, 1.75, 2, 2.5, 3, 5)},
        # reads off another stand-in delay D: landed within 2 s means refine_s <= 2 - D
        "landed_by_refine_s": {str(t): rate(A, lambda a: a["landed"] and a["refine_s"] is not None and a["refine_s"] <= t)["rate"] for t in (0.6, 0.8, 1, 1.2, 1.4, 1.6, 1.8, 2)},
        "phases_s_p50": {k: q([a.get(k) for a in A], 50)[0] for k in ("jump_s", "moves_s", "first_in_s", "last_in_s", "press_s")},
        "entered_more_than_once": sum(a.get("entries", 0) > 1 for a in A),
        "by_offset_deg": binned("offset_deg", [0, 0.75, 1.25, 2, 3, 99]),
        "by_distance_from_previous_pt": binned("from_prev_pt", [0, 300, 700, 9999]),
        "miss_beyond_edge_pt_p50_p90": q([a["miss_pt"] for a in misses], 50, 90),
        "cursor_sd_before_press_pt_p50_p90": q([a["steady_pt"] for a in pressed], 50, 90),
        "frame_to_cursor_ms_p50_p95": lat_ms,
    }


def report():
    for f in sorted((HERE / "results").glob("*.json")):
        r = json.loads(f.read_text())
        p = r["params"]
        head = f"{f.stem:28} {p['feature']:6} gain {p['g_lo']:g}-{p['g_hi']:g} over {p['v_lo']:g}-{p['v_hi']:g} px/s, y x{p['y_scale']:g}, {p['mincut']:g} Hz, rest {'on' if p['rest'] else 'off'}"
        if r["kind"] == "task":
            s = r["summary"]
            w = s["landed_within_2s"]
            print(f"{head}\n    offset {p['offset']:4} jump {p['jump_ms']:g} ms: {w['landed']}/{w['n']} within 2 s {w['ci95']}, {s['landed_any_time']['landed']} at any time, "
                  f"press p50 {s['press_s_p50_p90'][0]} s, refine p50 {s['refine_s_p50_p90'][0]} s")
        else:
            print(head)
            for phase, v in r["phases"].items():
                print(f"    {phase:6}" + "".join(f"  {k} sd {x['sd_pt']} p95 {x['p95_pt']} pt" for k, x in v["cursor"].items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--distance-cm", type=float, default=55, help="eye to screen, tape-measured")
    ap.add_argument("--seed", type=int, default=random.randrange(10**6))
    ap.add_argument("--auto", action="store_true", help="presses its own keys (smoke test)")
    ap.add_argument("--report", action="store_true")
    for k, v in asdict(Params()).items():
        if isinstance(v, bool):
            ap.add_argument(f"--no-{k}", dest=k, action="store_false")
        else:
            ap.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v, **({"choices": NAMES} if k == "feature" else {"choices": OFFSETS} if k == "offset" else {}))
    args = ap.parse_args()
    if args.report:
        report()
        raise SystemExit

import AppKit  # noqa: E402
import cv2  # noqa: E402
import Foundation  # noqa: E402
import mediapipe as mp  # noqa: E402
import Quartz  # noqa: E402
from mediapipe.tasks.python import BaseOptions  # noqa: E402
from mediapipe.tasks.python import vision as mpv  # noqa: E402

from capture import Camera  # noqa: E402

CG = Quartz.kCGEventSourceStateCombinedSessionState


def cursor():
    p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return p.x, p.y


def trackpad_moves():
    return Quartz.CGEventSourceCounterForEventType(CG, Quartz.kCGEventMouseMoved)


def poll_keys(downs, stop):
    """Key-down times and the cursor at each, to the millisecond: no permission, no key identities."""
    n = Quartz.CGEventSourceCounterForEventType(CG, Quartz.kCGEventKeyDown)
    while not stop.wait(0.001):
        m = Quartz.CGEventSourceCounterForEventType(CG, Quartz.kCGEventKeyDown)
        if m != n:
            downs.append((time.monotonic(), *cursor()))
            n = m


class Tracker(threading.Thread):
    """Every camera frame: landmarks, the controller, the cursor. One row of trace per frame."""

    COLS = 7  # pts, time of the cursor call, cursor x, y, speed, gain, waiting; then the features

    def __init__(self, cam, p, bounds):
        super().__init__(daemon=True)
        self.cam, self.p, self.lock = cam, p, threading.Lock()
        self.ctl, self.rows, self.t_rest = Controller(cursor(), bounds), [], None
        path = ROOT / "models" / "face_landmarker.task"
        if not path.exists():
            import urllib.request
            path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(URL, path)
        self.lm = mpv.FaceLandmarker.create_from_options(mpv.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)), running_mode=mpv.RunningMode.VIDEO, num_faces=1))

    def run(self):
        t0 = last = None
        while (item := self.cam.q.get()) is not None:
            pts, nv12 = item
            if nv12.shape != (SIZE[1] * 3 // 2, SIZE[0]):  # frames before the format is set
                continue
            t0 = pts if t0 is None else t0
            ms = last = int((pts - t0) * 1000) if last is None else max(int((pts - t0) * 1000), last + 1)
            r = self.lm.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(nv12, cv2.COLOR_YUV2RGB_NV12)), ms)
            F = np.full((len(NAMES), 2), np.nan)
            if r.face_landmarks:
                L = np.array([(l.x * SIZE[0], l.y * SIZE[1]) for l in r.face_landmarks[0]])
                F = np.array([L[i].mean(0) for i in FEATURES.values()])
            with self.lock:
                was = self.ctl.waiting
                c = self.ctl.step(pts, F[NAMES.index(self.p.feature)], self.p)
                Quartz.CGWarpMouseCursorPosition((float(c[0]), float(c[1])))
                now = time.monotonic()
                if was and not self.ctl.waiting:
                    self.t_rest = now
                self.rows.append((pts, now, c[0], c[1], self.ctl.speed, self.ctl.gain, self.ctl.waiting, *F.ravel()))

    def jump(self, to):
        with self.lock:
            self.ctl.jump(to, self.p)
            Quartz.CGWarpMouseCursorPosition((float(to[0]), float(to[1])))
            self.t_rest = None
            return time.monotonic()

    def trace(self, t0=0.0, t1=math.inf):
        with self.lock:
            R = np.array(self.rows[-20000:], float).reshape(-1, self.COLS + 2 * len(NAMES))
        return R[(R[:, 1] >= t0) & (R[:, 1] <= t1)]


class UI:
    def __init__(self, distance_cm):
        self.screen_pt = tuple(AppKit.NSScreen.mainScreen().frame().size)
        self.k = SCREEN_CM[0] / self.screen_pt[0]  # cm per point
        self.pt_per_deg = math.tan(math.radians(1)) * distance_cm / self.k
        cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(WIN, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        for _ in range(100):  # let the fullscreen transition settle
            cv2.imshow(WIN, np.zeros((10, 10, 3), np.uint8))
            cv2.waitKey(20)
        AppKit.NSApp().activateIgnoringOtherApps_(True)
        f = max((w.frame() for w in AppKit.NSApp().windows()), key=lambda f: f.size.width * f.size.height)
        self.rect = int(f.origin.x), int(self.screen_pt[1] - f.origin.y - f.size.height), int(f.size.width), int(f.size.height)

    def show(self, lines=(), target=None, dot=None, hud="", centred=False):
        """Window points, top-left origin. Returns once the image is handed to the window."""
        _, _, w, h = self.rect
        img = np.zeros((h, w, 3), np.uint8)
        if target:
            x, y = target
            cv2.rectangle(img, (x - HALF, y - HALF), (x + HALF - 1, y + HALF - 1), WHITE, -1)
        if dot:
            cv2.circle(img, dot, 7, WHITE, -1, cv2.LINE_AA)
            cv2.circle(img, dot, 2, (0, 0, 0), -1, cv2.LINE_AA)
        for j, s in enumerate(lines):
            x = (w - cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0]) // 2 if centred else 40
            cv2.putText(img, s, (x, (h // 2 - 14 * len(lines) if centred else 60) + 28 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.6, GREY, 1, cv2.LINE_AA)
        if hud:  # away from the hit target
            cv2.putText(img, hud, (40, 30 if not target or target[1] > h // 2 else h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, DIM, 1, cv2.LINE_AA)
        cv2.imshow(WIN, img)
        return self.key()

    def key(self, ms=1):
        return cv2.waitKey(ms) & 0xFF

    def wait(self, lines, auto):
        t0 = time.monotonic()
        while self.show(lines, centred=True) not in (SPACE, ESC, 13) and not (auto and time.monotonic() - t0 > 1):
            self.key(30)


@dataclass
class Session:
    ui: UI
    trk: Tracker
    p: Params
    rng: random.Random
    downs: deque
    out: Path
    name: str
    distance_cm: float
    auto: bool
    blocks: int = 0

    def save(self, kind, **kw):
        self.blocks += 1
        r = {"session": self.name, "kind": kind, "distance_cm": self.distance_cm, "pt_per_deg": round(self.ui.pt_per_deg, 2),
             "screen_pt": self.ui.screen_pt, "window": self.ui.rect, "camera": self.trk.cam.state(), "params": asdict(self.p), **kw}
        tag = f"offset-{self.p.offset}" if kind == "task" else "hold"
        (HERE / "results").mkdir(exist_ok=True)
        (HERE / "results" / f"{self.name}-{self.blocks:02d}-{tag}.json").write_text(json.dumps(r, indent=1))
        return r


def grid(nx, ny, w, h, rng, margin=HALF + 4):
    """(cell, x, y): one hit target at a random position in each cell, fully on screen."""
    return [([i, j], round(rng.uniform(max(margin, i * w / nx), min(w - margin, (i + 1) * w / nx))),
             round(rng.uniform(max(margin, j * h / ny), min(h - margin, (j + 1) * h / ny)))) for j in range(ny) for i in range(nx)]


def attempts(S, scored):
    ui, p, rng = S.ui, S.p, S.rng
    x0, y0, w, h = ui.rect
    cells = rng.sample(grid(9, 5, w, h, rng), 45)[: 4 if S.auto else 45]
    A, i, tally, last = [], 0, [0, 0], ""
    prev = cursor()
    hud = lambda: f"{i + 1}/{len(cells)}" if scored else f"practice, esc ends. {tally[0]}/{tally[1]} within 2 s. {last}"
    ui.show(hud=hud())
    t_next = time.monotonic() + rng.uniform(1, 2)
    while scored and i < len(cells) or not scored:
        cell, x, y = cells[i % len(cells)]
        while time.monotonic() < t_next:
            if ui.key() == ESC:
                return A
        gx, gy = x0 + x, y0 + y
        deg = rng.lognormvariate(math.log(1.5), SIGMA) if p.offset == "req" else float(p.offset)
        for _ in range(200):  # a direction that keeps the cursor on screen
            th = rng.uniform(0, 2 * math.pi)
            to = gx + deg * ui.pt_per_deg * math.cos(th), gy + deg * ui.pt_per_deg * math.sin(th)
            if x0 + 2 <= to[0] <= x0 + w - 3 and y0 + 2 <= to[1] <= y0 + h - 3:
                break
        moves = trackpad_moves()
        ui.show(target=(x, y), hud=hud())
        t_on = time.monotonic()
        t_jump = t_press = pos = None
        while True:
            now = time.monotonic()
            if t_jump is None and now >= t_on + p.jump_ms / 1000:
                t_jump = S.trk.jump(to)
            k = ui.key()
            if k == ESC:
                ui.show(hud=hud())
                return A
            if k == SPACE or (S.auto and now > t_on + 0.9):
                d = S.downs[-1] if S.downs and S.downs[-1][0] >= t_on else (now, *cursor())
                t_press, pos = d[0], d[1:]
                break
            if now > t_on + CAP_S:
                break
        ui.show(hud=hud())
        t_next = (t_press or time.monotonic()) + rng.uniform(1, 2)
        a = {"i": i, "cell": cell, "x": gx, "y": gy, "offset_deg": round(deg, 3), "jump_to": [round(v, 1) for v in to],
             "from_prev_pt": round(math.dist(prev, (gx, gy)), 1), "t_on": t_on,
             "jump_s": t_jump and round(t_jump - t_on, 4), "press_s": t_press and round(t_press - t_on, 4),
             "refine_s": t_press and t_jump and t_jump < t_press and round(t_press - t_jump, 4) or None,
             "rest_s": None, "landed": False, "trackpad": trackpad_moves() != moves, "cursor": None, "miss_pt": None, "steady_pt": None}
        if t_jump and S.trk.t_rest and (not t_press or S.trk.t_rest <= t_press):
            a["rest_s"] = round(S.trk.t_rest - t_jump, 4)
        if t_press:
            dx, dy = pos[0] - gx, pos[1] - gy
            a["cursor"] = [round(pos[0], 1), round(pos[1], 1)]
            a["landed"] = -HALF <= dx < HALF and -HALF <= dy < HALF and not a["trackpad"]
            a["miss_pt"] = round(max(abs(dx), abs(dy)) - HALF, 1)
            T = S.trk.trace(t_press - 1, t_press)[-N_STEADY:, 2:4]
            a["steady_pt"] = round(float(np.sqrt(T.var(0).sum())), 2) if len(T) > 2 else None
            if t_jump:  # phases, seconds after the hit target appeared
                T = S.trk.trace(t_jump, t_press)
                t, inside = T[:, 1] - t_on, (np.abs(T[:, 2] - gx) < HALF) & (np.abs(T[:, 3] - gy) < HALF)
                moving = t[(T[:, 6] == 0) & (T[:, 4] > p.rest_speed)]
                a["moves_s"] = round(float(moving[0]), 3) if len(moving) else None
                a["first_in_s"] = round(float(t[inside][0]), 3) if inside.any() else None
                k = len(inside)
                while k and inside[k - 1]:
                    k -= 1
                a["last_in_s"] = round(float(t[k]), 3) if k < len(inside) else None
                a["entries"] = int((np.diff(np.r_[0, inside.astype(int)]) == 1).sum())
            prev = pos
        ok = a["landed"] and a["press_s"] <= LIMIT_S
        tally = [tally[0] + ok, tally[1] + 1]
        last = f"last: {'landed' if a['landed'] else 'missed' if t_press else 'no press'} at {a['press_s']} s from {deg:.1f} deg"
        A.append(a)
        i += 1
    return A


def task(S, scored):
    t0 = time.monotonic()
    A = attempts(S, scored)
    if not scored or not A:
        return
    lat = S.trk.trace(t0)
    s = summarise(A, q((lat[:, 1] - lat[:, 0]) * 1e3, 50, 95))
    r = S.save("task", summary=s, attempts=A)
    print(json.dumps({"params": r["params"], "summary": s}, indent=1))
    w, e = s["landed_within_2s"], s["landed_any_time"]
    S.ui.wait([f"{w['landed']} of {w['n']} landed within 2 s ({100 * w['rate']:.0f}%, 95% interval {w['ci95'][0]:.2f} to {w['ci95'][1]:.2f}); the requirement is 95%.",
               f"{e['landed']} landed at any time, {s['no_press_in_5s']} without a press, {s['trackpad']} with the trackpad touched.",
               f"Press {s['press_s_p50_p90'][0]} s median, {s['press_s_p50_p90'][1]} s p90; jump to press {s['refine_s_p50_p90'][0]} s median.",
               f"By starting offset (deg): " + ", ".join(f"{k}: {v['landed']}/{v['n']}" for k, v in s["by_offset_deg"].items() if v["n"]),
               "Medians from the hit target appearing: jump {jump_s} s, head moves {moves_s} s, first inside {first_in_s} s, last entry {last_in_s} s, press {press_s} s.".format(**s["phases_s_p50"]),
               f"{s['entered_more_than_once']} attempts overshot and came back.",
               "", "space returns to free play"], S.auto)


def hold(S):
    """How far the cursor strays with no jump: head still, then through small and large gaze shifts."""
    ui, p, rng = S.ui, S.p, S.rng
    x0, y0, w, h = ui.rect
    secs = 2 if S.auto else 10
    phases = {"still": "Keep your eyes on the mark and your head still.",
              "near": "Follow the mark with your eyes as it hops nearby. Move as you naturally would.",
              "far": "Follow the mark with your eyes as it hops across the screen. Move as you naturally would."}
    R = {}
    for name, how in phases.items():
        ui.wait([f"Hold test, {name}: {secs} s.", how, "Do not steer the cursor.", "", "space starts"], S.auto)
        x, y = w // 2, h // 2
        t0 = t_hop = time.monotonic()
        ui.show(dot=(x, y))
        while (now := time.monotonic()) < t0 + secs:
            if name != "still" and now > t_hop + 1:
                for _ in range(200):
                    r, th = rng.uniform(2, 4) * ui.pt_per_deg, rng.uniform(0, 2 * math.pi)
                    nx, ny = (round(x + r * math.cos(th)), round(y + r * math.sin(th))) if name == "near" else (rng.randrange(20, w - 20), rng.randrange(20, h - 20))
                    if 20 <= nx < w - 20 and 20 <= ny < h - 20:
                        break
                x, y, t_hop = nx, ny, now
                ui.show(dot=(x, y))
            if ui.key(5) == ESC:
                return
        T = S.trk.trace(t0, t0 + secs)
        F = T[:, Tracker.COLS:].reshape(len(T), len(NAMES), 2)
        R[name] = {"frames": len(T), "feature_range_px": {}, "cursor": {}}
        for j, k in enumerate(NAMES):  # the same frames through every feature
            c = Controller(T[0, 2:4], (-1e9, -1e9, 1e9, 1e9))
            C = np.array([c.step(t, f, p).copy() for t, f in zip(T[:, 0], F[:, j])])
            far = np.linalg.norm(C - C[0], axis=1)
            R[name]["feature_range_px"][k] = round(float(np.linalg.norm(np.nanpercentile(F[:, j], 97.5, 0) - np.nanpercentile(F[:, j], 2.5, 0))), 2)
            R[name]["cursor"][k] = {"sd_pt": round(float(np.sqrt(C.var(0).sum())), 2), "p95_pt": round(float(np.percentile(far, 95)), 2), "end_pt": round(float(far[-1]), 2)}
    S.save("hold", phases=R)
    print(json.dumps(R, indent=1))
    S.ui.wait(["Cursor straying, SD and p95 from its start, in points (the hit target reaches 12 from its centre):"]
              + [f"{n:6}" + "".join(f"   {k}: {v['sd_pt']:5.1f} {v['p95_pt']:5.1f}" for k, v in r["cursor"].items()) for n, r in R.items()]
              + ["", "space returns to free play"], S.auto)


KEYS = {  # key: (parameter, step); a factor when it ends in x
    "[": ("g_lo", -0.25), "]": ("g_lo", 0.25), "-": ("g_hi", -0.5), "=": ("g_hi", 0.5), ";": ("v_hi", -10), "'": ("v_hi", 10),
    "9": ("y_scale", -0.1), "0": ("y_scale", 0.1), ",": ("mincut", "0.8x"), ".": ("mincut", "1.25x"), "1": ("rest_speed", -2), "2": ("rest_speed", 2),
    "3": ("rest_min_ms", -50), "4": ("rest_min_ms", 50),
}


def free(S):
    ui, p, shown = S.ui, S.p, 0
    while True:
        if time.monotonic() - shown > 0.1:
            T = S.trk.trace(time.monotonic() - 1)
            sd = float(np.sqrt(T[:, 2:4].var(0).sum())) if len(T) > 2 else 0
            lat = q((T[:, 1] - T[:, 0]) * 1e3, 50)[0]
            lost = len(T) == 0 or np.isnan(T[-1, Tracker.COLS])
            k = ui.show([
                f"PROTOTYPE refinement (#21). {S.distance_cm:g} cm, 1 deg = {ui.pt_per_deg:.0f} pt, the hit target is 24 pt.",
                "",
                f"feature   f       {p.feature}",
                f"gain      [ ]     {p.g_lo:g} pt/px while the head is slower than {p.v_lo:g} px/s",
                f"          - =     {p.g_hi:g} pt/px once it is faster than {p.v_hi:g} px/s  (; ')",
                f"vertical  9 0     x {p.y_scale:.1f}",
                f"filter    , .     {p.mincut:.2f} Hz at rest",
                f"rest rule r       {'on' if p.rest else 'off'}: after a jump, ignore the head {p.rest_min_ms:g} ms (3 4), then until {p.rest_frames} frames under {p.rest_speed:g} px/s (1 2)",
                f"offset    o       {p.offset}" + (" (median 1.5, p90 3 deg)" if p.offset == "req" else " deg"),
                f"jump              {p.jump_ms:g} ms after the hit target appears",
                "",
                "face lost: the cursor holds" if lost else f"now: head {S.trk.ctl.speed:5.1f} px/s, gain {S.trk.ctl.gain:.1f}, cursor SD over 1 s {sd:5.1f} pt, frame to cursor {lat} ms",
                "",
                "p practice    b scored block of 45    h hold test    esc quit",
            ])
            shown = time.monotonic()
        else:
            k = ui.key(5)
        c = chr(k)
        if k == ESC or S.auto:
            if S.auto:
                task(S, True)
                hold(S)
            return
        if c in KEYS:
            name, step = KEYS[c]
            v = getattr(p, name)
            v = v * float(step[:-1]) if isinstance(step, str) else v + step
            setattr(p, name, round(min(max(v, {"v_hi": p.v_lo + 2, "rest_min_ms": 0}.get(name, 0.1)), 1000), 3))
        elif c == "f":
            p.feature = NAMES[(NAMES.index(p.feature) + 1) % len(NAMES)]
        elif c == "o":
            p.offset = OFFSETS[(OFFSETS.index(p.offset) + 1) % len(OFFSETS)]
        elif c == "r":
            p.rest = not p.rest
        elif c in "pb":
            task(S, c == "b")
        elif c == "h":
            hold(S)


def main(a):
    p = Params(**{k: getattr(a, k) for k in asdict(Params())})
    name = f"{datetime.now():%Y%m%d-%H%M%S}{'-auto' if a.auto else ''}"
    out = ROOT / "refinement" / name
    out.mkdir(parents=True)
    awake = Foundation.NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
        Foundation.NSActivityUserInitiated | Foundation.NSActivityLatencyCritical | Foundation.NSActivityIdleDisplaySleepDisabled, "refinement")
    ui = UI(a.distance_cm)
    x0, y0, w, h = ui.rect
    cam = Camera(SIZE).start()
    trk = Tracker(cam, p, (x0, y0, x0 + w - 1, y0 + h - 1))
    trk.start()
    downs, stop = deque(maxlen=64), threading.Event()
    poller = threading.Thread(target=poll_keys, args=(downs, stop))
    poller.start()
    S = Session(ui, trk, p, random.Random(a.seed), downs, out, name, a.distance_cm, a.auto)
    try:
        free(S)
    finally:
        stop.set()
        poller.join()
        cam.stop()
        cam.q.put(None)
        trk.join()
        cv2.destroyAllWindows()
        for _ in range(20):
            cv2.waitKey(10)
        Foundation.NSProcessInfo.processInfo().endActivity_(awake)
        T = np.array(trk.rows, float).reshape(-1, Tracker.COLS + 2 * len(NAMES))
        np.savez_compressed(out / "trace.npz", trace=T, columns=np.array(["pts", "t_cursor", "x", "y", "speed", "gain", "waiting"] + [f"{k}_{c}" for k in NAMES for c in "xy"]))
        (out / "meta.json").write_text(json.dumps({"session": name, "seed": a.seed, "distance_cm": a.distance_cm, "params_at_exit": asdict(p), "camera": cam.state(), "frames": len(T)}, indent=1))
        flags = " ".join(f"--no-{k}" if v is False else f"--{k.replace('_', '-')} {v}" for k, v in asdict(p).items() if v is not True)
        print(f"{out}\n{len(T)} frames, {cam.state()['drops']} drops\nthese settings again: uv run refine.py --distance-cm {a.distance_cm:g} {flags}")


if __name__ == "__main__":
    main(args)
