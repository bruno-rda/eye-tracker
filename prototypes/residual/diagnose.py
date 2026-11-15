# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "matplotlib"]
# ///
"""PROTOTYPE, throwaway. Splits the offset left after a linear calibration among its suspects (#17).

  uv run diagnose.py [../../recordings/pilot/20261114-222639] [--head ../../recordings/pilot/20261114-231201-head]

Reads the features.npz that ../pilot/replay.py cached; decodes no video. Prints tables and writes
results/<session>.json and results/<session>.png. Loading and scoring are copied from replay.py so
the floors match.

Head-compensated: a feature minus what head yaw and pitch add to it, the slopes taken inside
fixations of a head block, where the target is fixed and only the head moves.
Ceiling: calibrated on the block it is scored on, leave one fixation out.
"""

import argparse
import json
from itertools import combinations_with_replacement
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PILOT = HERE.parents[1] / "recordings" / "pilot"
EYES = ((33, 133, 468), (362, 263, 473))  # corner, corner, iris centre
LIDS = ((159, 145), (386, 374))  # upper, lower
RIGID = (168, 6, 197, 195, 5, 4, 10, 151, 9, 8)  # nose ridge and forehead midline
WINDOW, BUDGET_S, BLINK, FACE = 30, 30.0, 0.4, 0.5
rng = np.random.default_rng(0)


# ---- copied from ../pilot/replay.py ----

def session(events):
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


def per_eye(L):
    """Iris centre minus eye-corner midpoint in the corner-line frame, per eye, px."""
    out = []
    for a, b, iris in EYES:
        u = L[:, b] - L[:, a]
        u = u / np.linalg.norm(u, axis=1, keepdims=True)
        off = L[:, iris] - (L[:, a] + L[:, b]) / 2
        out.append(np.stack([(off * u).sum(1), off[:, 1] * u[:, 0] - off[:, 0] * u[:, 1]], 1))
    return out


def budget(pool):
    nx, ny = (max(f["cell"][k] for f in pool) + 1 for k in (0, 1))
    outer = lambda f: f["cell"][0] in (0, (nx - 1) // 2, nx - 1) and f["cell"][1] in (0, (ny - 1) // 2, ny - 1)
    chosen, used = [], 0.0
    for f in sorted(pool, key=lambda f: not outer(f)):
        cost = f["t_press"] + (WINDOW + 1) / 30 - f["t_on"]
        if used + cost <= BUDGET_S:
            chosen.append(f)
            used += cost
    return chosen


def unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def ang(a, b):
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a, b), axis=-1), (a * b).sum(-1)))


def rays(xy, d, eye=(0.0, 0.0)):
    """Unit vectors from an eye at distance d, opposite screen point `eye`, to screen points in cm."""
    xy = np.atleast_2d(xy) - np.asarray(eye)
    return unit(np.c_[xy, np.full(len(xy), -d)])


# ---- features ----

def load(d):
    d = Path(d).resolve()
    F = dict(np.load(d / "features.npz"))
    pts = np.loadtxt(d / "frames.csv", delimiter=",", ndmin=2)[:, 0]
    events = [json.loads(l) for l in (d / "events.jsonl").read_text().splitlines()]
    L, M = F["lm"].astype(float), F["pose"].astype(float)
    bad = (F["blink"].mean(1) > BLINK) | (F["face"] < FACE) | np.isnan(L[:, 0, 0])
    eyes = per_eye(L)
    width = np.mean([np.linalg.norm(L[:, b] - L[:, a], axis=1) for a, b, _ in EYES], 0)
    u = unit(L[:, 263] - L[:, 33])  # face x axis in the image
    frame = lambda v: np.stack([(v * u).sum(1), v[:, 1] * u[:, 0] - v[:, 0] * u[:, 1]], 1)
    ref = L[:, RIGID].mean(1)
    iris = (L[:, 468] + L[:, 473]) / 2
    corners = L[:, [33, 133, 362, 263]].mean(1)
    lid = lambda k: np.mean([frame(L[:, l[k]] - (L[:, a] + L[:, b]) / 2)[:, 1] for l, (a, b, _) in zip(LIDS, EYES)], 0)
    X = {
        "eye": np.mean(eyes, 0),
        "eyes": np.c_[eyes[0], eyes[1]],
        "eye/width": np.mean(eyes, 0) / width[:, None] * np.nanmedian(width),
        "lids": np.c_[lid(0), lid(1)],
        "iris-rigid": frame(iris - ref),
        "corners-rigid": frame(corners - ref),
        "yawpitch": np.degrees(np.stack([np.arctan2(M[:, 0, 2], M[:, 2, 2]), np.arcsin(np.clip(-M[:, 1, 2], -1, 1))], 1)),
        "roll": np.degrees(np.arctan2(M[:, 1, 0], M[:, 1, 1]))[:, None],
        "shift": M[:, :3, 3],
        "width": width[:, None],
    }
    X["head"] = np.c_[X["yawpitch"], X["roll"], X["shift"]]
    B = session(events)
    for name, b in B.items():
        for f in b["fix"]:
            p = np.searchsorted(pts, f["t_press"])
            i = np.clip(p + np.arange(WINDOW), 0, len(pts) - 1)
            f["i"], f["block"], f["d"] = i[~bad[i]], name, b["distance_cm"]
            f["still"] = (lambda j: j[~bad[j]])(np.clip(p - 10 + np.arange(10), 0, len(pts) - 1))
            f["moving"] = (lambda j: j[~bad[j]])(np.clip(p + np.arange(120), 0, len(pts) - 1))
    pursuit = [(np.searchsorted(pts, e["t"]), e["x_cm"], e["y_cm"]) for e in events if e["kind"] == "pursuit"]
    return {"X": X, "B": B, "bad": bad, "pts": pts, "pursuit": pursuit, "name": d.name}


def cols(S, names):
    return np.concatenate([S["X"][n] for n in names], 1)


def poly(x, degree):
    out = [x]
    if degree == 2:
        out.append(np.stack([x[:, i] * x[:, j] for i, j in combinations_with_replacement(range(x.shape[1]), 2)], 1))
    return np.concatenate(out, 1)


def fit(x, y, lam=1.0, degree=1):
    """Ridge on standardised columns; returns a predictor."""
    x = poly(x, degree)
    mu, sd = x.mean(0), x.std(0) + 1e-9
    Z = np.c_[(x - mu) / sd, np.ones(len(x))]
    W = np.linalg.solve(Z.T @ Z + np.diag([lam] * x.shape[1] + [0.0]), Z.T @ y)
    return lambda q: np.c_[(poly(q, degree) - mu) / sd, np.ones(len(q))] @ W


def frames(fix, key="i"):
    return np.concatenate([f[key] for f in fix]), np.concatenate([np.tile(f["xy"], (len(f[key]), 1)) for f in fix])


def offsets(x, fix, predict, eye=(0.0, 0.0), dd=0.0):
    """Per fixation: the mean estimate's offset as a vector in degrees (x, y) and its size."""
    v, o = [], []
    for f in fix:
        e = predict(x[f["i"]]).mean(0)
        d = f["d"] + dd
        v.append(np.degrees(np.arctan((e - eye) / d) - np.arctan((f["xy"] - eye) / d)))
        o.append(float(ang(rays(e, d, eye)[0], rays(f["xy"], d, eye)[0])))
    return np.array(v), np.array(o)


def med(o):
    return round(float(np.median(o)), 2)


def ci(o, stat=np.median, reps=2000):
    return [round(float(v), 2) for v in np.percentile([stat(rng.choice(o, len(o))) for _ in range(reps)], [2.5, 97.5])]




def within(S, fix, names, key="moving", reach=None):
    """Frames of fixations held through head movement, each minus its fixation's mean: the target cancels."""
    out = {n: [] for n in names}
    for f in fix:
        i = f[key]
        if reach is not None:  # only frames whose head turn stays within `reach` degrees of the still pose
            turn = np.linalg.norm(S["X"]["yawpitch"][i] - S["X"]["yawpitch"][f["still"]].mean(0), axis=1)
            i = i[turn < reach]
        if len(i) < 10:
            continue
        for n in names:
            out[n].append(S["X"][n][i] - S["X"][n][i].mean(0))
    return {n: np.concatenate(v) for n, v in out.items()}


def lstsq(a, b):
    return np.linalg.lstsq(a, b, rcond=None)[0]


def r2(y, yhat):
    return round(float(1 - ((y - yhat) ** 2).sum() / ((y - y.mean(0)) ** 2).sum()), 2)


def compensated(S, names, T, fix, hname="yawpitch", reach=6):
    """Features as they would read at the pool's mean head pose; head slopes from T's head block."""
    w = within(T, fix, names + [hname], reach=reach)
    K = lstsq(w[hname], np.concatenate([w[n] for n in names], 1))
    return cols(S, names) - (S["X"][hname] - np.nanmean(S["X"][hname][frames(S["B"]["pool"]["fix"])[0]], 0)) @ K


def forward(x, y):
    """Features as a linear function of the target, inverted: no dilution from noisy features."""
    T = np.c_[y, np.ones(len(y))]
    A = lstsq(T, x)
    Ci = np.linalg.inv(np.atleast_2d(np.cov((x - T @ A).T)))
    G = np.linalg.solve(A[:2] @ Ci @ A[:2].T, A[:2] @ Ci)
    return lambda q: (q - A[2]) @ G.T


def cell(v, o):
    return [med(o), med(np.abs(v[:, 0])), med(np.abs(v[:, 1]))]


def main(a):
    S, H = load(a.session), load(a.head)
    B = S["B"]
    pool, early, late, head = (B[k]["fix"] for k in ("pool", "early", "late", "head"))
    hfix = H["B"]["head"]["fix"]
    pool10 = budget(pool)
    tests = {"early": early, "late": late}
    R = {"session": S["name"], "head_session": H["name"]}
    show = lambda title, rows: print(f"\n{title}\n" + "\n".join(f"  {k:<50} {json.dumps(v)}" for k, v in rows.items()))
    gaze = lambda fix: np.array([np.degrees(np.arctan(f["xy"] / f["d"])) for f in fix])

    def run(x, train, test, how="ridge", **kw):
        i, y = frames(train)
        return offsets(x, test, forward(x[i], y) if how == "forward" else fit(x[i], y, **kw))

    def loo(x, test, **kw):
        r = [run(x, test[:k] + test[k + 1:], [f], **kw) for k, f in enumerate(test)]
        return np.array([v[0] for v, _ in r]), np.array([o[0] for _, o in r])

    # 1. the floor and the shape of its offsets
    x = cols(S, ["eye"])
    R["floor"] = {}
    for name, test in tests.items():
        v, o = run(x, pool10, test, lam=0.0)
        halves = [run(x, pool10, [{**f, "i": f["i"][s]} for f in test], lam=0.0)[0] for s in (slice(0, 15), slice(15, 30))]
        i, y = frames(pool10)
        est = np.array([fit(x[i], y, lam=0.0)(x[f["i"]]).mean(0) for f in test])
        tg = np.array([f["xy"] for f in test])
        R["floor"][name] = {
            "median_x_y_deg": cell(v, o), "ci": ci(o), "p90_deg": round(float(np.percentile(o, 90)), 2),
            "mean_offset_xy_deg": v.mean(0).round(2).tolist(), "sd_xy_deg": v.std(0).round(2).tolist(),
            "share_of_squared_offset_vertical": round(float((v[:, 1] ** 2).sum() / (v ** 2).sum()), 2),
            "estimate_per_unit_target_xy": [round(float(np.polyfit(tg[:, k], est[:, k], 1)[0]), 2) for k in (0, 1)],
            "half_window_disagreement_sd_xy_deg": (halves[0] - halves[1]).std(0).round(2).tolist(),
        }
    show("1. floor: linear, iris minus corners, 10 pool fixations. median_x_y = [offset, |x|, |y|]", R["floor"])

    # 2. how much of each gaze shift the head makes
    R["head_share"] = {}
    for name, fix in {"pool": pool, **tests}.items():
        g, h = gaze(fix), np.array([S["X"]["yawpitch"][f["i"]].mean(0) for f in fix])
        R["head_share"][name] = {}
        for k, axis in ((0, "yaw per deg of gaze x"), (1, "pitch per deg of gaze y")):
            s = np.polyfit(g[:, k], h[:, k], 1)
            R["head_share"][name][axis] = {"slope": round(float(abs(s[0])), 2), "r": round(float(np.corrcoef(g[:, k], h[:, k])[0, 1]), 2),
                                           "leftover_sd_deg": round(float((h[:, k] - np.polyval(s, g[:, k])).std()), 2)}
    show("2. the head's share of the gaze shift, per block", R["head_share"])

    # 3. head slopes where the target is fixed and the head moves
    R["head_slopes"] = {}
    for sname, (T, fix) in {"session head block": (S, head), "re-record head block": (H, hfix)}.items():
        for reach in (None, 6):
            w = within(T, fix, ["eye", "yawpitch"], reach=reach)
            K = lstsq(w["yawpitch"], w["eye"])
            R["head_slopes"][f"{sname}, turns {'all' if reach is None else '< 6 deg'}"] = {
                "frames": len(w["eye"]), "yaw_pitch_sd_deg": w["yawpitch"].std(0).round(1).tolist(),
                "eye_x_px_per_deg_yaw": round(float(K[0, 0]), 3), "eye_y_px_per_deg_pitch": round(float(K[1, 1]), 3),
                "r2": r2(w["eye"], w["yawpitch"] @ K)}
    show("3. eye feature against head pose inside head-block fixations", R["head_slopes"])

    # 4. the ladder: what each fix buys
    X = {
        "eye (floor)": x,
        "eye, head-compensated": compensated(S, ["eye"], H, hfix),
        "eye + lids": cols(S, ["eye", "lids"]),
        "eye + lids, head-compensated": compensated(S, ["eye", "lids"], H, hfix),
        "  same, slopes from the session's head block": compensated(S, ["eye", "lids"], S, head),
        "each eye + lids, head-compensated": compensated(S, ["eyes", "lids"], H, hfix),
    }
    R["ladder"] = {n: {"pool 10": [cell(*run(v, pool10, t, lam=0.0)) for t in tests.values()],
                       "pool 25": [cell(*run(v, pool, t, lam=0.0)) for t in tests.values()],
                       "ceiling": [cell(*loo(v, t, lam=0.0)) for t in tests.values()]} for n, v in X.items()}
    print("\n4. ladder: [offset, |x|, |y|] median deg, early then late")
    for n, row in R["ladder"].items():
        print(f"  {n:<46}" + "".join(f"  {k}: {row[k][0]} {row[k][1]}" for k in row))
    O = {n: {b: run(X[n], pool, t, lam=0.0)[1] for b, t in tests.items()} for n in X}
    R["paired"] = {f"{p} minus {q}": {b: {"mean_deg": round(float(np.mean(O[p][b] - O[q][b])), 2), "ci": ci(O[p][b] - O[q][b], np.mean)} for b in tests}
                   for p, q in (("eye (floor)", "eye, head-compensated"), ("eye, head-compensated", "eye + lids, head-compensated"),
                                ("eye (floor)", "eye + lids, head-compensated"))}
    show("   paired differences, pool 25", R["paired"])
    best = X["eye + lids, head-compensated"]
    R["after_fixes"] = {}
    for name, test in tests.items():
        v, o = run(best, pool, test, lam=0.0)
        halves = [run(best, pool, [{**f, "i": f["i"][s]} for f in test], lam=0.0)[0] for s in (slice(0, 15), slice(15, 30))]
        R["after_fixes"][name] = {"mean_offset_xy_deg": v.mean(0).round(2).tolist(), "sd_xy_deg": v.std(0).round(2).tolist(),
                                  "median_without_mean_offset_deg": med(np.linalg.norm(v - v.mean(0), axis=1)),
                                  "half_window_disagreement_sd_xy_deg": (halves[0] - halves[1]).std(0).round(2).tolist()}
    show("   eye + lids, head-compensated, pool 25: what is left", R["after_fixes"])

    # 5. suspects that explain nothing
    lap = [{"i": np.array([i]), "xy": np.array([px, py])} for i, px, py in S["pursuit"] if not S["bad"][i]]
    i, y = frames(pool10)
    in_angles = fit(x[i], np.degrees(np.arctan(y / 51.0)), lam=0.0)
    geo = fit(x[i], y, lam=0.0)
    two = lambda f: [med(f(t)) for t in tests.values()]
    R["no_help"] = {
        "floor": two(lambda t: run(x, pool10, t, lam=0.0)[1]),
        "25 pool fixations": two(lambda t: run(x, pool, t, lam=0.0)[1]),
        "25 + pursuit lap": two(lambda t: run(x, pool + lap, t, lam=0.0)[1]),
        "quadratic, 25": two(lambda t: run(x, pool, t, degree=2)[1]),
        "forward fit, 25": two(lambda t: run(x, pool, t, how="forward")[1]),
        "eye over eye width": two(lambda t: run(cols(S, ["eye/width"]), pool10, t, lam=0.0)[1]),
        "fitted in angles, not cm": two(lambda t: offsets(x, t, lambda q: 51.0 * np.tan(np.radians(in_angles(q))))[1]),
        "scored with the eye opposite the top edge": two(lambda t: offsets(x, t, geo, np.array([0, -9.82]))[1]),
        "scored at 46 cm": two(lambda t: offsets(x, t, geo, dd=-5.0)[1]),
        "scored at 56 cm": two(lambda t: offsets(x, t, geo, dd=5.0)[1]),
        "ceiling, linear": two(lambda t: loo(x, t, lam=0.0)[1]),
        "ceiling, quadratic": two(lambda t: loo(x, t, degree=2)[1]),
        "yaw and pitch fitted on the pool, 10": two(lambda t: run(cols(S, ["eye", "yawpitch"]), pool10, t)[1]),
        "yaw and pitch fitted on the pool, 25": two(lambda t: run(cols(S, ["eye", "yawpitch"]), pool, t)[1]),
        "head pose 6 fitted on the pool, 10": two(lambda t: run(cols(S, ["eye", "head"]), pool10, t)[1]),
        "head pose 6 fitted on the pool, 25": two(lambda t: run(cols(S, ["eye", "head"]), pool, t)[1]),
    }
    show("5. calibration model, calibration data, screen geometry, head terms fitted on the pool: floor median [early, late]", R["no_help"])

    # 6. landmark motion per degree of gaze with head pose held: pool, test blocks and both head blocks
    fixs = [(S, f) for f in pool + early + late] + [(S, {**f, "i": f["moving"]}) for f in head] + [(H, {**f, "i": f["moving"]}) for f in hfix]
    rows = lambda n: np.concatenate([T["X"][n][f["i"]] for T, f in fixs])
    g = np.concatenate([np.tile(np.degrees(np.arctan(f["xy"] / f["d"])), (len(f["i"]), 1)) for _, f in fixs])
    grp = np.concatenate([np.full(len(f["i"]), k) for k, (_, f) in enumerate(fixs)])
    A = np.c_[g, rows("head"), np.concatenate([np.full(len(f["i"]), float(T is H)) for T, f in fixs]), np.ones(len(g))]
    R["landmarks"] = {}
    for n, label in (("iris-rigid", "iris from rigid landmarks"), ("corners-rigid", "eye corners from rigid landmarks"),
                     ("eye", "iris minus corners"), ("lids", "upper lid minus corners")):
        yv = rows(n)
        C = lstsq(A, yv)
        boot = []
        for _ in range(300):
            j = np.concatenate([np.flatnonzero(grp == k) for k in rng.choice(len(fixs), len(fixs))])
            boot.append(lstsq(A[j], yv[j])[:2])
        lo, hi = np.percentile(boot, [2.5, 97.5], 0)
        kx, ky = ((0, 0), (1, 0)) if n == "lids" else ((0, 0), (1, 1))
        R["landmarks"][label] = {"px_per_deg_horizontal": [round(float(abs(C[kx])), 3), sorted(round(float(abs(q[kx])), 3) for q in (lo, hi))] if n != "lids" else None,
                                 "px_per_deg_vertical": [round(float(abs(C[ky])), 3), sorted(round(float(abs(q[ky])), 3) for q in (lo, hi))],
                                 "unexplained_sd_as_deg_vertical": round(float((yv - A @ C).std(0)[ky[1]] / abs(C[ky])), 1)}
    show("6. landmark motion per degree of gaze, head pose held [value, 95% interval over fixations]", R["landmarks"])

    # 7. ceilings, and how far head pose alone predicts the target
    R["ceilings"] = {n: [cell(*loo(v, t)) for t in tests.values()] for n, v in {
        "eye": x, "eye + lids, head-compensated": best,
        "each eye + lids + head pose 6": cols(S, ["eyes", "lids", "head"]),
        "iris from rigid landmarks + lids + head pose 6": cols(S, ["iris-rigid", "lids", "head"]),
        "head pose 6 alone": cols(S, ["head"])}.items()}
    show("7. ceilings [offset, |x|, |y|], early then late", R["ceilings"])

    # 8. stray in the session's head block
    R["stray"] = {}
    for n, v in (("eye (floor)", x), ("eye + lids, head-compensated", best)):
        i, y = frames(pool)
        predict = fit(v[i], y, lam=0.0)
        s, turn = [], []
        for f in head:
            ref = predict(v[f["still"]]).mean(0)
            s += list(ang(rays(predict(v[f["moving"]]), f["d"]), rays(ref, f["d"])[0]))
            turn += list(np.linalg.norm(S["X"]["yawpitch"][f["moving"]] - S["X"]["yawpitch"][f["still"]].mean(0), axis=1))
        s, turn = np.array(s), np.array(turn)
        R["stray"][n] = {f"{lo}-{hi}": round(float(np.median(s[(turn >= lo) & (turn < hi)])), 1) for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 7), (7, 12), (12, 90))}
    show("8. stray in the session's head block, median deg by head turn deg", R["stray"])

    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"{S['name']}.json").write_text(json.dumps(R, indent=1))

    # figure: each arrow runs from a fixation target to the mean estimate
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(15, 7.6), sharex=True, sharey=True)
    for r, (bname, test) in enumerate(tests.items()):
        for c, n in enumerate(("eye (floor)", "eye, head-compensated", "eye + lids, head-compensated")):
            i, y = frames(pool)
            predict = fit(X[n][i], y, lam=0.0)
            tg = np.array([f["xy"] for f in test])
            est = np.array([predict(X[n][f["i"]]).mean(0) for f in test])
            ax[r, c].quiver(tg[:, 0], tg[:, 1], *(est - tg).T, angles="xy", scale_units="xy", scale=1, width=0.004, color="#1f6feb")
            ax[r, c].plot(tg[:, 0], tg[:, 1], "k.", ms=4)
            ax[r, c].add_patch(plt.Rectangle((-15.12, -9.82), 30.24, 19.64, fill=False, lw=0.5))
            ax[r, c].set_title(f"{bname}: {n}, median {med(O[n][bname])} deg", fontsize=10)
            ax[r, c].set_aspect("equal")
    ax[0, 0].invert_yaxis()
    fig.supxlabel("screen cm; each arrow runs from a fixation target to the estimate; 25 pool fixations; 1 deg is about 0.9 cm")
    fig.tight_layout()
    fig.savefig(HERE / "results" / f"{S['name']}.png", dpi=110)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("session", type=Path, nargs="?", default=PILOT / "20261114-222639")
    p.add_argument("--head", type=Path, default=PILOT / "20261114-231201-head")
    main(p.parse_args())
