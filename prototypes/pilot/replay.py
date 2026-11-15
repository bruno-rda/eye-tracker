# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "mediapipe==1.2.2"]
# ///
"""PROTOTYPE, throwaway. Replays a pilot session through two simple estimators and sizes the protocol (#15).

  uv run replay.py ../../recordings/pilot/<session> [--blink 0.4] [--face 0.5]

The first run decodes every frame, checks its CRC and caches landmarks, blink and face scores in
features.npz (about 5 min); later runs only report. Beside the recording it writes results.json and
two contact sheets for the referee spot check, referee-blink.png and referee-face.png.

Estimators, each calibrated on the pool fixations that fit the 30 s budget:
  centre    the screen centre, a constant
  eye       linear in iris minus eye corners (the one-degree prototype's calibration)
  eye+head  the same plus head yaw and pitch from MediaPipe's face transform, ridge
"""

import argparse
import json
import random
import subprocess
import sys
import time
import urllib.request
import zlib
from collections import defaultdict
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mpv

HERE = Path(__file__).resolve().parent
MODELS = HERE.parents[1] / "recordings" / "models"
URLS = {
    "face_landmarker.task": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
}
EYES = ((33, 133, 468), (362, 263, 473))  # corner, corner, iris centre
WINDOW, BUDGET_S, TILES = 30, 30.0, 8
rng = np.random.default_rng(0)


def model(name):
    if not (MODELS / name).exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(URLS[name], MODELS / name)
    return BaseOptions(model_asset_path=str(MODELS / name))


def decode(d, w, h):
    n = w * h * 3 // 2
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(d / "frames.mkv"), "-fps_mode", "passthrough",
                          "-f", "rawvideo", "-pix_fmt", "nv12", "-"], stdout=subprocess.PIPE)
    while len(b := p.stdout.read(n)) == n:
        yield np.frombuffer(b, np.uint8).reshape(h * 3 // 2, w)


def sheet(path, bins, label):
    """Contact sheet: one row per score bin."""
    if not bins:
        return
    th, tw = next(iter(bins.values()))[0].shape[:2]
    rows = []
    for b in sorted(bins):
        row = np.zeros((th, 90 + TILES * tw, 3), np.uint8)
        cv2.putText(row, label(b), (4, th // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        for j, t in enumerate(bins[b]):
            row[:, 90 + j * tw : 90 + (j + 1) * tw] = t
        rows.append(row)
    cv2.imwrite(str(path), np.vstack(rows))


def extract(d, meta, pts, crc):
    """One pass over the frames: landmarks, head transform, blink and face scores, CRC check, sample tiles."""
    w, h = meta["size"]
    lm = mpv.FaceLandmarker.create_from_options(mpv.FaceLandmarkerOptions(
        base_options=model("face_landmarker.task"), running_mode=mpv.RunningMode.VIDEO, num_faces=1,
        output_face_blendshapes=True, output_facial_transformation_matrixes=True))
    det = mpv.FaceDetector.create_from_options(mpv.FaceDetectorOptions(
        base_options=model("blaze_face_short_range.tflite"), min_detection_confidence=0.05))
    N = len(pts)
    F = {"lm": np.full((N, 478, 2), np.nan, np.float32), "pose": np.full((N, 4, 4), np.nan, np.float32),
         "blink": np.full((N, 2), np.nan, np.float32), "face": np.zeros(N, np.float32),
         "ms": np.zeros(N, np.float32), "crc_ok": np.zeros(N, bool)}
    tiles, seen, pick, names = {"blink": defaultdict(list), "face": defaultdict(list)}, defaultdict(int), random.Random(0), None

    def keep(kind, b, make):  # reservoir sample per score bin
        seen[kind, b] += 1
        if len(tiles[kind][b]) < TILES:
            tiles[kind][b].append(make())
        elif pick.random() < TILES / seen[kind, b]:
            tiles[kind][b][pick.randrange(TILES)] = make()

    def tag(img, s):
        cv2.putText(img, s, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        return img

    t_start = time.perf_counter()
    for i, nv12 in zip(range(N), decode(d, w, h)):
        F["crc_ok"][i] = zlib.crc32(nv12) == crc[i]
        rgb = cv2.cvtColor(nv12, cv2.COLOR_YUV2RGB_NV12)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        t0 = time.perf_counter()
        r = lm.detect_for_video(img, int((pts[i] - pts[0]) * 1000))
        F["ms"][i] = (time.perf_counter() - t0) * 1e3
        F["face"][i] = max((x.categories[0].score for x in det.detect(img).detections), default=0)
        keep("face", int(min(F["face"][i], 0.999) * 10), lambda: tag(cv2.cvtColor(cv2.resize(rgb, (240, 135)), cv2.COLOR_RGB2BGR), f"{F['face'][i]:.2f} #{i}"))
        if not r.face_landmarks:
            continue
        p = F["lm"][i] = np.array([(l.x * w, l.y * h) for l in r.face_landmarks[0]], np.float32)
        F["pose"][i] = r.facial_transformation_matrixes[0]
        names = names or {c.category_name: j for j, c in enumerate(r.face_blendshapes[0])}
        F["blink"][i] = [r.face_blendshapes[0][names[k]].score for k in ("eyeBlinkLeft", "eyeBlinkRight")]
        s = float(F["blink"][i].mean())

        def eyes():
            c, half = (p[33] + p[263]) / 2, 0.75 * np.linalg.norm(p[263] - p[33])
            x0, y0 = int(max(0, c[0] - half)), int(max(0, c[1] - half * 0.375))
            crop = rgb[y0 : y0 + int(half * 0.75), x0 : x0 + int(2 * half)]
            return tag(cv2.cvtColor(cv2.resize(crop, (256, 96)), cv2.COLOR_RGB2BGR), f"{s:.2f} #{i}")

        if 0 < p[33, 0] < p[263, 0] < w and 0 < p[33, 1] < h:
            keep("blink", int(min(s, 0.999) * 10), eyes)
        if i % 1000 == 999:
            print(f"{i + 1}/{N} frames, {(i + 1) / (time.perf_counter() - t_start):.0f} fps", file=sys.stderr)
    F["decoded"] = np.array(i + 1)
    np.savez(d / "features.npz", **F)
    sheet(d / "referee-blink.png", tiles["blink"], lambda b: f"{b / 10:.1f}-{(b + 1) / 10:.1f}")
    sheet(d / "referee-face.png", tiles["face"], lambda b: f"{b / 10:.1f}-{(b + 1) / 10:.1f}")
    return F


def session(events):
    """Blocks by name: distance, start, end, fixations (a redo overwrites)."""
    B = {}
    for e in events:
        k = e["kind"]
        if k == "block_start":
            B[e["block"]] = {"distance_cm": e["distance_cm"], "t0": e["t"], "t1": None, "fix": {}}
        elif k == "target_on":
            B[e["block"]]["fix"][e["i"]] = {"cell": e["cell"], "xy": np.array([e["x_cm"], e["y_cm"]]), "t_on": e["t"]}
        elif k == "press":
            B[e["block"]]["fix"][e["i"]]["t_press"] = e["t"]
        elif k == "block_end":
            B[e["block"]]["t1"] = e["t"]
    for b in B.values():
        b["fix"] = [f for _, f in sorted(b["fix"].items()) if "t_press" in f]
        b["t1"] = b["t1"] or events[-1]["t"]
    return B


def eye_feature(L):
    """Iris centre minus eye-corner midpoint in the corner-line frame, mean of both eyes, px."""
    out = []
    for a, b, iris in EYES:
        u = L[:, b] - L[:, a]
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        off = L[:, iris] - (L[:, a] + L[:, b]) / 2
        out.append(np.stack([(off * u).sum(1), off[:, 1] * u[:, 0] - off[:, 0] * u[:, 1]], 1))
    return np.mean(out, 0)


def head_angles(M):
    """Yaw and pitch in degrees from the face transform."""
    return np.degrees(np.stack([np.arctan2(M[:, 0, 2], M[:, 2, 2]), np.arcsin(np.clip(-M[:, 1, 2], -1, 1))], 1))


def budget(pool):
    """Pool fixations fitting 30 s of recorded time (onset to end of retained window): the 3 x 3 subgrid first."""
    nx, ny = (max(f["cell"][k] for f in pool) + 1 for k in (0, 1))
    outer = lambda f: f["cell"][0] in (0, (nx - 1) // 2, nx - 1) and f["cell"][1] in (0, (ny - 1) // 2, ny - 1)
    chosen, used = [], 0.0
    for f in sorted(pool, key=lambda f: not outer(f)):
        cost = f["t_press"] + (WINDOW + 1) / 30 - f["t_on"]
        if used + cost <= BUDGET_S:
            chosen.append(f)
            used += cost
    return chosen, used


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def ang(a, b):
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b), axis=-1), (a * b).sum(-1)))


def rays(xy, d):
    """Unit vectors from an eye opposite the screen centre at distance d to screen points in cm."""
    xy = np.atleast_2d(xy)
    return unit(np.c_[xy, np.full(len(xy), -d)])


def score(E, target, d):
    """Offset of the mean estimate from the fixation target, and the spread of the estimates, in degrees."""
    E = E[~np.isnan(E[:, 0])]
    if len(E) < 3:
        return dict(offset=np.nan, offset_cm=np.nan, std=np.nan, rms=np.nan)
    g = rays(E, d)
    m = rays(E.mean(0), d)[0]
    return dict(offset=float(ang(m, rays(target, d)[0])), offset_cm=float(np.linalg.norm(E.mean(0) - target)),
                std=float(np.sqrt((ang(g, m) ** 2).mean())), rms=float(np.sqrt((ang(g[1:], g[:-1]) ** 2).mean())))


def ci(x, stat, n=None, reps=2000):
    """Percentile bootstrap 95% interval; n resamples to another sample size."""
    x = np.asarray(x)
    s = [stat(rng.choice(x, n or len(x))) for _ in range(reps)]
    return [round(float(v), 2) for v in np.percentile(s, [2.5, 97.5])]


def runs(flag):
    """Lengths of the runs of True."""
    e = np.diff(np.r_[0, flag.astype(int), 0])
    return np.flatnonzero(e == -1) - np.flatnonzero(e == 1)


def q(x, *ps):
    x = np.asarray(x, float)
    return [round(float(v), 2) for v in np.nanpercentile(x, ps)] if np.isfinite(x).any() else [None] * len(ps)


def report(d, meta, pts, F, events, a):
    B = session(events)
    R = {"session": d.name, "light": meta.get("light"), "thresholds": {"blink": a.blink, "face": a.face}}
    win = lambda f, n=WINDOW, shift=0: np.clip(np.searchsorted(pts, f["t_press"]) + shift + np.arange(n), 0, len(pts) - 1)
    span = lambda t0, t1: np.arange(np.searchsorted(pts, t0), np.searchsorted(pts, t1))
    blink = F["blink"].mean(1)
    is_blink, lost = blink > a.blink, F["face"] < a.face
    flagged = is_blink | lost

    # recording
    dt = np.diff(pts)
    sizes = np.array(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "packet=size", "-of", "csv=p=0",
                                     str(d / "frames.mkv")], capture_output=True, text=True).stdout.split(), float)
    gbmin = lambda idx: round(float(sizes[idx[idx < len(sizes)]].mean() * 1800 / 1e9), 3) if len(idx) else None
    gap_t = [e["t"] for e in events if e["kind"] in ("gap_start", "gap_end")]
    R["recording"] = {
        "minutes": round((pts[-1] - pts[0]) / 60, 1), "frames": len(pts), "drops": meta.get("camera", {}).get("drops"),
        "pts_gaps_after_2s": int((dt[60:] > 1.5 / 30).sum()), "backlog_max": meta.get("backlog_max"),
        "crc_ok": f"{int(F['crc_ok'].sum())}/{int(F['decoded'])}", "gb": round(sizes.sum() / 1e9, 2),
        "gb_per_min": {"session": gbmin(np.arange(len(pts))), **{k: gbmin(span(b["t0"], b["t1"])) for k, b in B.items()},
                       **({"gap": gbmin(span(*gap_t))} if len(gap_t) == 2 else {})},
        "landmarker_ms_p95": q(F["ms"], 95)[0],
    }
    if a.codecs and "head" in B:  # other lossless encodings of 30 s of the head block
        t0 = np.searchsorted(pts, B["head"]["t0"]) / 30
        for name, args in {"ffv1_intra": ["-c:v", "ffv1", "-level", "3", "-g", "1"], "x264_medium": ["-c:v", "libx264", "-preset", "medium", "-qp", "0"]}.items():
            tmp, t = d / "tmp.mkv", time.perf_counter()
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t0), "-t", "30", "-i", str(d / "frames.mkv"), *args, str(tmp)])
            R["recording"]["gb_per_min"][name + "_head_30s"] = round(tmp.stat().st_size * 2 / 1e9, 3)
            R["recording"][name + "_fps"] = round(900 / (time.perf_counter() - t))
            tmp.unlink()

    # timing
    prompts = {e["block"]: e["t"] for e in events if e["kind"] == "prompt"}
    R["timing"] = {}
    for k, b in B.items():
        on = np.array([f["t_on"] for f in b["fix"]])
        press = np.array([f["t_press"] for f in b["fix"]])
        R["timing"][k] = {"fixations": len(on), "onset_to_press_s": q(press - on, 50, 90), "per_fixation_s": q(np.diff(on), 50, 90),
                          "block_s": round(b["t1"] - b["t0"], 1), "setup_s": round(b["t0"] - prompts[k], 1)}

    # referee
    R["referee"] = {
        "blink_score_percentiles_1_50_90_99": q(blink, 1, 50, 90, 99),
        "blink_score_p50_in_windows_by_row": {},
        "blink": {str(t): {"flagged": round(float((blink > t).mean()), 4), "events": int(len(runs(blink > t))),
                           "event_frames_p50_p90": q(runs(blink > t), 50, 90)} for t in (0.3, 0.4, 0.5, 0.6, 0.7)},
        "face_score_percentiles_1_10_50": q(F["face"], 1, 10, 50),
        "face": {str(t): round(float((F["face"] < t).mean()), 4) for t in (0.3, 0.5, 0.7, 0.9)},
        "no_landmarks": round(float(np.isnan(F["lm"][:, 0, 0]).mean()), 4),
    }
    by_row = defaultdict(list)
    for k in ("early", "late"):
        for f in B.get(k, {"fix": []})["fix"]:
            by_row[f["cell"][1]].append(np.nanmedian(blink[win(f)]))
    R["referee"]["blink_score_p50_in_windows_by_row"] = {str(r): q(v, 50)[0] for r, v in sorted(by_row.items())}

    # estimators
    pool = B["pool"]["fix"]
    chosen, used = budget(pool)
    R["calibration"] = {"pool": len(pool), "in_budget": len(chosen), "budget_s_used": round(used, 1)}
    idx = np.concatenate([win(f) for f in chosen])
    Y = np.concatenate([np.tile(f["xy"], (WINDOW, 1)) for f in chosen])
    ok = ~flagged[idx] & ~np.isnan(F["lm"][idx, 0, 0])
    X = {"eye": eye_feature(F["lm"]), "eye+head": np.c_[eye_feature(F["lm"]), head_angles(F["pose"])]}
    P = {"centre": np.where(np.isnan(F["lm"][:, :1, 0]), np.nan, 0.0) * np.ones((1, 2))}
    for name, x in X.items():
        mu, sd = x[idx][ok].mean(0), x[idx][ok].std(0)
        Z = np.c_[(x - mu) / sd, np.ones(len(x))]
        lam = np.diag([1.0 * (name == "eye+head")] * x.shape[1] + [0.0])
        W = np.linalg.solve(Z[idx][ok].T @ Z[idx][ok] + lam, Z[idx][ok].T @ Y[ok])
        P[name] = Z @ W

    def scores(block, n=WINDOW, shift=0):
        b, out = B[block], {k: [] for k in P}
        dropped = 0
        for f in b["fix"]:
            i = win(f, n, shift)
            if flagged[i].mean() > 0.5:
                dropped += 1
                continue
            for k in P:
                out[k].append(score(P[k][i[~flagged[i]]], f["xy"], b["distance_cm"]))
        return out, dropped

    R["accuracy"], offsets = {}, {}
    for block in ("early", "late"):
        if block not in B:
            continue
        S, dropped = scores(block)
        frames = span(B[block]["t0"], B[block]["t1"])
        seen_ = frames[~flagged[frames]]
        R["accuracy"][block] = {"distance_cm": B[block]["distance_cm"], "fixations": len(B[block]["fix"]), "dropped": dropped,
                                "flagged_frames": round(float(flagged[frames].mean()), 4)}
        for k, s in S.items():
            off = offsets[block, k] = np.array([x["offset"] for x in s])
            R["accuracy"][block][k] = {
                "median_deg": q(off, 50)[0], "median_ci": ci(off, np.nanmedian), "p90_deg": q(off, 90)[0],
                "p90_ci": ci(off, lambda v: np.nanpercentile(v, 90)), "median_cm": q([x["offset_cm"] for x in s], 50)[0],
                "std_deg": q([x["std"] for x in s], 50)[0], "rms_deg": q([x["rms"] for x in s], 50)[0],
                "data_loss": round(float(np.isnan(P[k][seen_, 0]).mean()), 4)}

    # sizing: the paired spread between estimators, and how tight 45, 90 and 180 fixations are
    R["sizing"] = {}
    blocks = [b for b in ("early", "late") if b in B]
    if blocks:
        both = {k: np.concatenate([offsets[b, k] for b in blocks]) for k in P}
        for x, y in (("eye", "eye+head"), ("centre", "eye")):
            diff = both[x] - both[y]
            diff = diff[~np.isnan(diff)]
            sd = float(diff.std(ddof=1))
            R["sizing"][f"{x} minus {y}"] = {
                "n": len(diff), "mean_deg": round(float(diff.mean()), 2), "ci": ci(diff, np.mean), "paired_sd_deg": round(sd, 2),
                "per_block_sd": [round(float(np.nanstd(offsets[b, x] - offsets[b, y], ddof=1)), 2) for b in blocks],
                "n_for_0.3_deg_ci": int(np.ceil((1.96 * sd / 0.3) ** 2)), "n_for_0.3_deg_power_80": int(np.ceil((2.8 * sd / 0.3) ** 2))}
        e = both["eye"][~np.isnan(both["eye"])]
        R["sizing"]["eye_interval_width_by_n"] = {
            str(n): {"median": ci(e, np.median, n), "p90": ci(e, lambda v: np.percentile(v, 90), n)} for n in (45, 90, 180)}
        R["sizing"]["retained_window"] = {
            "median_deg_by_shift_frames": {str(s): q([x["offset"] for x in scores(blocks[0], shift=s)[0]["eye"]], 50)[0] for s in (-15, -6, 0, 3, 6)},
            "median_deg_by_length_frames": {str(n): q([x["offset"] for x in scores(blocks[0], n=n)[0]["eye"]], 50)[0] for n in (10, 20, 30)},
            "std_deg_by_length_frames": {str(n): q([x["std"] for x in scores(blocks[0], n=n)[0]["eye"]], 50)[0] for n in (10, 20, 30)}}

    # head block: how far each estimate strays from where it sat before the head moved
    if "head" in B:
        b, n = B["head"], int(meta.get("head_s", 4) * 30)
        H = {"fixations": len(b["fix"]), "distance_cm": b["distance_cm"]}
        yp, tr, nose = head_angles(F["pose"]), F["pose"][:, :3, 3], F["lm"][:, 168]
        move, turn, strays = defaultdict(list), [], defaultdict(list)
        for f in b["fix"]:
            i = win(f, n)
            still = win(f, 10, -10)
            reach = lambda v: float(np.diff(np.nanpercentile(v, [5, 95]))[0])
            move["yaw_range_deg"].append(reach(yp[i, 0]))
            move["pitch_range_deg"].append(reach(yp[i, 1]))
            move["translation_range_cm"].append(np.hypot(reach(tr[i, 0]), reach(tr[i, 1])))
            move["nose_range_px"].append(np.hypot(reach(nose[i, 0]), reach(nose[i, 1])))
            turn += list(np.linalg.norm(yp[i] - np.nanmean(yp[still], 0), axis=1))
            for k in P:
                ref = np.nanmean(P[k][still], 0)
                stray = ang(rays(P[k][i][~np.isnan(P[k][i, 0])], b["distance_cm"]), rays(ref, b["distance_cm"])[0])
                strays[k] += list(ang(rays(P[k][i], b["distance_cm"]), rays(ref, b["distance_cm"])[0]))
                move[k, "p50"].append(np.median(stray))
                move[k, "p95"].append(np.percentile(stray, 95))
                move[k, "still_offset"].append(score(P[k][still], f["xy"], b["distance_cm"])["offset"])
        H["movement_median"] = {k: q(v, 50)[0] for k, v in move.items() if isinstance(k, str)}
        H["stray_deg"] = {k: {"p50": q(move[k, "p50"], 50)[0], "p95": q(move[k, "p95"], 50)[0], "worst_p95": q(move[k, "p95"], 100)[0],
                              "offset_while_still": q(move[k, "still_offset"], 50)[0]} for k in P}
        turn = np.array(turn)  # the head's turn from its pose before the press, yaw and pitch combined
        H["stray_deg_median_p90_by_head_turn_deg"] = {
            f"{lo}-{hi}": {"frames": int(((turn >= lo) & (turn < hi)).sum()),
                           **{k: q(np.array(strays[k])[(turn >= lo) & (turn < hi)], 50, 90) for k in P if k != "centre"}}
            for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 7), (7, 12), (12, 20), (20, 90))}
        R["head"] = H

    R["gap"] = {k: sum(e["kind"] == k and len(gap_t) == 2 and gap_t[0] <= e["t"] <= gap_t[1] for e in events) for k in ("click", "right_click", "key", "cursor")}
    (d / "results.json").write_text(json.dumps(R, indent=1))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{d.name}.json").write_text(json.dumps(R, indent=1))
    print(json.dumps(R, indent=1))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("session", type=Path)
    p.add_argument("--blink", type=float, default=0.4, help="referee: mean eye-blink score above this is a blink")
    p.add_argument("--face", type=float, default=0.5, help="referee: face detection score below this is face lost")
    p.add_argument("--codecs", action="store_true", help="also size FFV1 and x264 medium on 30 s of the head block")
    a = p.parse_args()
    d = a.session.resolve()
    meta = json.loads((d / "meta.json").read_text())
    rows = np.loadtxt(d / "frames.csv", delimiter=",", ndmin=2)
    pts, crc = rows[:, 0], rows[:, 1].astype(np.uint32)
    events = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines()]
    F = dict(np.load(d / "features.npz")) if (d / "features.npz").exists() else extract(d, meta, pts, crc)
    report(d, meta, pts, F, events, a)
