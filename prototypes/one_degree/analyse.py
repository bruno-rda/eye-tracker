# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "opencv-python", "mediapipe==1.2.2", "pyobjc-framework-Vision", "pyobjc-framework-Quartz"]
# ///
"""PROTOTYPE, throwaway. Replays a recorded session through the candidate landmark models (#8).

  uv run analyse.py recordings/one-degree/<session>

Estimators: MediaPipe Face Landmarker IMAGE (unfiltered) and VIDEO (one-euro filtered), Apple Vision
revision 3, and `native`: a limbus-gradient centre fit on the native-resolution luma, seeded by MediaPipe.
References: `raw` is the iris centre in the image, `eye` is the iris centre minus the eye-corner midpoint.
Both are the mean of the two eyes. Per-frame noise is mapped to degrees through the px/deg slope fitted
across fixations, so precision in degrees needs no camera intrinsics.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import Vision
from Foundation import NSData
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision as mpv

MODEL = Path(__file__).resolve().parents[2] / "recordings" / "models" / "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
EYES = [  # MediaPipe mesh indices: corners (image-left, image-right), iris centre, iris contour, lids
    dict(corners=(33, 133), iris=468, contour=(469, 470, 471, 472), lids=(159, 145)),
    dict(corners=(362, 263), iris=473, contour=(474, 475, 476, 477), lids=(386, 374)),
]
IRIS_MM = 11.71  # #2


def landmarker(mode):
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    o = mpv.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=mode, num_faces=1)
    return mpv.FaceLandmarker.create_from_options(o)


def mp_eyes(res, w, h):
    """Per eye: iris, corner a, corner b, openness, iris diameter. None if no face."""
    if not res.face_landmarks:
        return None
    p = np.array([(l.x * w, l.y * h) for l in res.face_landmarks[0]])
    out = []
    for e in EYES:
        a, b = p[e["corners"][0]], p[e["corners"][1]]
        c = p[list(e["contour"])]
        diam = (np.linalg.norm(c[0] - c[2]) + np.linalg.norm(c[1] - c[3])) / 2
        open_ = np.linalg.norm(p[e["lids"][0]] - p[e["lids"][1]]) / np.linalg.norm(b - a)
        out.append((p[e["iris"]], a, b, open_, diam))
    return out


def vision_eyes(bgr):
    h, w = bgr.shape[:2]
    buf = cv2.imencode(".bmp", bgr)[1]
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(NSData.dataWithBytes_length_(buf.tobytes(), len(buf)), {})
    req = Vision.VNDetectFaceLandmarksRequest.alloc().init()
    req.setRevision_(Vision.VNDetectFaceLandmarksRequestRevision3)
    handler.performRequests_error_([req], None)
    if not req.results():
        return None
    obs = req.results()[0]
    bb, lm = obs.boundingBox(), obs.landmarks()

    def pts(region):
        n = region.pointCount()
        q = region.normalizedPoints()
        return np.array([((bb.origin.x + q[i].x * bb.size.width) * w, (1 - bb.origin.y - q[i].y * bb.size.height) * h) for i in range(n)])

    out = []
    for eye, pupil in ((lm.leftEye(), lm.leftPupil()), (lm.rightEye(), lm.rightPupil())):
        if eye is None or pupil is None:
            return None
        c = pts(eye)
        a, b = c[c[:, 0].argmin()], c[c[:, 0].argmax()]
        out.append((pts(pupil).mean(0), a, b, np.ptp(c[:, 1]) / np.linalg.norm(b - a), np.nan))
    return sorted(out, key=lambda e: e[0][0])  # image-left eye first, as MediaPipe


def limbus_centre(gray, seed, r):
    """Point maximising mean squared alignment of outward gradients in an annulus around the seed."""
    k = int(np.ceil(1.6 * r))
    x0, y0 = int(round(seed[0])) - k, int(round(seed[1])) - k
    crop = gray[y0 : y0 + 2 * k + 1, x0 : x0 + 2 * k + 1].astype(np.float32)
    gx, gy = cv2.Sobel(crop, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(crop, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    yy, xx = np.mgrid[: crop.shape[0], : crop.shape[1]]
    s = np.array(seed) - (x0, y0)
    dist = np.hypot(xx - s[0], yy - s[1])
    m = (dist > 0.6 * r) & (dist < 1.4 * r) & (mag > mag.mean() + 0.5 * mag.std())
    P = np.stack([xx[m], yy[m]], 1).astype(np.float32)
    G = np.stack([gx[m], gy[m]], 1) / mag[m][:, None]

    def best(centre, half, step):
        g = np.arange(-half, half + step / 2, step)
        C = np.stack(np.meshgrid(g, g), -1).reshape(-1, 2) + centre
        D = P[None] - C[:, None]
        D /= np.linalg.norm(D, axis=2, keepdims=True) + 1e-6
        obj = (np.clip((D * G[None]).sum(2), 0, None) ** 2).mean(1)
        return C[obj.argmax()]

    c = best(s, 0.5 * r, 0.5)
    c = best(c, 0.5, 0.05)
    return c + (x0, y0)


def features(eyes):
    """raw: mean iris centre. eye: mean of iris minus corner midpoint, in the corner-line frame."""
    raw = np.mean([e[0] for e in eyes], 0)
    rel = []
    for iris, a, b, *_ in eyes:
        u = (b - a) / np.linalg.norm(b - a)
        off = iris - (a + b) / 2
        rel.append((off @ u, off @ np.array([-u[1], u[0]])))
    diam = [e[4] for e in eyes if not np.isnan(e[4])]
    return raw, np.mean(rel, 0), np.mean([e[3] for e in eyes]), np.mean(diam) if diam else np.nan


def run_estimators(frames, pts, img_lm, vid_lm):
    """Returns {estimator: list of per-frame (raw, eye, openness, iris_px) or None}, and ms per frame."""
    out = {k: [] for k in ("mp_image", "mp_video", "vision", "native")}
    ms = {k: [] for k in out}
    for nv12, t in zip(frames, pts):
        h = nv12.shape[0] * 2 // 3
        rgb = cv2.cvtColor(nv12, cv2.COLOR_YUV2RGB_NV12)
        w = rgb.shape[1]
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        t0 = time.perf_counter()
        e = mp_eyes(img_lm.detect(img), w, h)
        ms["mp_image"].append((time.perf_counter() - t0) * 1e3)
        out["mp_image"].append(e and features(e))

        t0 = time.perf_counter()
        n = e and [(limbus_centre(nv12[:h], iris, diam / 2), a, b, o, diam) for iris, a, b, o, diam in e]
        ms["native"].append((time.perf_counter() - t0) * 1e3)
        out["native"].append(n and features(n))

        t0 = time.perf_counter()
        v = mp_eyes(vid_lm.detect_for_video(img, int(t * 1000)), w, h)
        ms["mp_video"].append((time.perf_counter() - t0) * 1e3)
        out["mp_video"].append(v and features(v))

        t0 = time.perf_counter()
        a = vision_eyes(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        ms["vision"].append((time.perf_counter() - t0) * 1e3)
        out["vision"].append(a and features(a))
    return out, {k: float(np.median(v)) for k, v in ms.items()}


def analyse_formats(d, meta):
    img_lm = landmarker(mpv.RunningMode.IMAGE)
    dist_mm = meta["distance_cm"] * 10
    print(f"{'format':>10} {'iris px':>8} {'corner px':>10} {'iris/width %':>13} {'HFOV deg':>9} {'vision':>7}")
    rows = []
    for c in meta["captures"]:
        z = np.load(d / c["file"])
        fr = z["nv12"]
        h = fr.shape[1] * 2 // 3
        w = fr.shape[2]
        iris, span, vis = [], [], 0
        for nv12 in fr:
            rgb = cv2.cvtColor(nv12, cv2.COLOR_YUV2RGB_NV12)
            e = mp_eyes(img_lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)), w, h)
            if e:
                iris.append(np.mean([x[4] for x in e]))
                span.append(np.mean([np.linalg.norm(x[2] - x[1]) for x in e]))
            vis += vision_eyes(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)) is not None
        ip = float(np.median(iris)) if iris else float("nan")
        hfov = float(np.degrees(2 * np.arctan(w / (2 * dist_mm * ip / IRIS_MM))))  # rough: iris size and distance assumed
        rows.append({"format": f"{w}x{h}", "iris_px": ip, "corner_px": float(np.median(span)) if span else None,
                     "iris_pct_width": 100 * ip / w, "hfov_deg_rough": hfov, "vision_faces": vis, "camera": c["camera"]})
        r = rows[-1]
        print(f"{r['format']:>10} {ip:8.1f} {r['corner_px'] or float('nan'):10.1f} {r['iris_pct_width']:13.2f} {hfov:9.1f} {vis:>4}/{len(fr)}")
    (d / "results.json").write_text(json.dumps(rows, indent=1))


def stats(per_fix, deg):
    """per_fix: list of (n_i, 2) arrays in px. deg: (k, 2) target angles. Returns the summary dict."""
    m = np.array([x.mean(0) for x in per_fix])
    X = np.c_[deg, np.ones(len(deg))]
    W = np.linalg.lstsq(X, m, rcond=None)[0]
    A, b = W[:2].T, W[2]  # px = A @ deg + b
    Ai = np.linalg.inv(A)
    sd, s2s, sd3, sdpx = [], [], [], []
    for x in per_fix:
        y = (x - x.mean(0)) @ Ai.T
        sd.append(y.std(0, ddof=1))
        s2s.append(np.sqrt((np.diff(y, axis=0) ** 2).mean(0)))
        k = len(y) // 3 * 3
        sd3.append(y[:k].reshape(-1, 3, 2).mean(1).std(0, ddof=1))
        sdpx.append(x.std(0, ddof=1))
    loo = []
    for i in range(len(m)):
        keep = np.arange(len(m)) != i
        Wi = np.linalg.lstsq(X[keep], m[keep], rcond=None)[0]
        loo.append(np.linalg.solve(Wi[:2].T, m[i] - Wi[2]) - deg[i])
    loo = np.array(loo)
    med = lambda a: np.median(np.array(a), 0).round(3).tolist()
    return {
        "px_per_deg": np.linalg.norm(A, axis=0).round(3).tolist(),
        "sd_px": med(sdpx),
        "sd_deg": med(sd),
        "rms_s2s_deg": med(s2s),
        "sd_deg_3frame_mean": med(sd3),
        "loo_offset_deg_median": float(np.median(np.linalg.norm(loo, axis=1)).round(3)),
        "loo_offset_deg_p90": float(np.percentile(np.linalg.norm(loo, axis=1), 90).round(3)),
    }


def analyse_fixations(d, meta):
    img_lm, vid_lm = landmarker(mpv.RunningMode.IMAGE), landmarker(mpv.RunningMode.VIDEO)
    fix = meta["fixations"]
    per = {}
    timing = []
    for f in fix:
        z = np.load(d / f["file"])
        out, ms = run_estimators(z["nv12"], z["pts"], img_lm, vid_lm)
        timing.append(ms)
        for k, rows in out.items():
            per.setdefault(k, []).append(rows)
        print(f"{f['file']} done", file=sys.stderr)
    deg = np.array([f["deg"] for f in fix])
    res = {"session": d.name, "n_fixations": len(fix), "camera": meta.get("camera"),
           "ms_per_frame": {k: round(float(np.median([t[k] for t in timing])), 1) for k in per}}
    for k, fixes in per.items():
        kept, lost, iris = {"raw": [], "eye": []}, [0, 0], []
        for rows in fixes:
            ok = [r for r in rows if r is not None]
            op = np.median([r[2] for r in ok]) if ok else 0
            ok = [r for r in ok if r[2] > 0.75 * op]  # drop blinks
            lost[0] += len(rows) - len(ok)
            lost[1] += len(rows)
            kept["raw"].append(np.array([r[0] for r in ok]))
            kept["eye"].append(np.array([r[1] for r in ok]))
            iris += [r[3] for r in ok]
        good = [i for i, x in enumerate(kept["raw"]) if len(x) >= 10]
        res[k] = {"data_loss": round(lost[0] / lost[1], 3), "iris_px": round(float(np.nanmedian(iris)), 1) if iris else None}
        for ref in ("raw", "eye"):
            res[k][ref] = stats([kept[ref][i] for i in good], deg[good])
    (d / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print(f"\n{'estimator':>9} {'ref':>4} {'px/deg x,y':>13} {'SD px x,y':>12} {'SD deg x,y':>12} {'3-frame SD deg':>15} {'LOO deg med/p90':>16}")
    for k in per:
        for ref in ("raw", "eye"):
            s = res[k][ref]
            f2 = lambda v: f"{v[0]:.2f},{v[1]:.2f}"
            print(f"{k:>9} {ref:>4} {f2(s['px_per_deg']):>13} {f2(s['sd_px']):>12} {f2(s['sd_deg']):>12} {f2(s['sd_deg_3frame_mean']):>15} {s['loo_offset_deg_median']:>7.2f}/{s['loo_offset_deg_p90']:.2f}")


if __name__ == "__main__":
    d = Path(sys.argv[1]).resolve()
    meta = json.loads((d / "meta.json").read_text())
    {"formats": analyse_formats, "fixations": analyse_fixations}[meta["kind"]](d, meta)
