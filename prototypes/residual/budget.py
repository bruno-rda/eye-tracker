# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "matplotlib"]
# ///
"""PROTOTYPE, throwaway. How could the 30 s calibration budget be split? (#18)

  uv run budget.py

Reuses diagnose.py and the features.npz that ../pilot/replay.py cached. Scores the head-compensated
estimator with eyelid landmarks on the pilot's test blocks, calibrated on static fixations, held
fixations or both. The session's head block is last in the session, so rows that use it are not causal.
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagnose as D  # noqa: E402

rng = np.random.default_rng(1)
S = D.load(D.PILOT / "20261114-222639")
H = D.load(D.PILOT / "20261114-231201-head")
B = S["B"]
pool, early, late, head = (B[k]["fix"] for k in ("pool", "early", "late", "head"))
hfix = H["B"]["head"]["fix"]
tests = {"early": early, "late": late}
NAMES = ["eye", "lids"]
med = lambda o: float(np.median(o))


def cost(f, hold):
    return f["t_press"] - f["t_on"] + hold


print("cost per fixation, s (onset to end of window)")
print("  pool static   ", np.round([np.mean([cost(f, 31 / 30) for f in pool]), np.std([cost(f, 31 / 30) for f in pool])], 2))
for n, fx in (("session head", head), ("re-record head", hfix)):
    print(f"  {n:<14}", "acquire", np.round(np.mean([f["t_press"] - f["t_on"] for f in fx]), 2), "+ 4 s hold =", np.round(np.mean([cost(f, 4.0) for f in fx]), 2))
print("  head block cells, session:", [tuple(f["cell"]) for f in head])
print("  head block cells, re-record:", [tuple(f["cell"]) for f in hfix])


def slopes(T, fix, dur=4.0, reach=6):
    """Head slopes from the first `dur` seconds of each head-held fixation."""
    rows = {n: [] for n in NAMES + ["yawpitch"]}
    for f in fix:
        i = f["moving"]
        i = i[i < (i[0] if len(i) else 0) + int(dur * 30)] if len(i) else i
        turn = np.linalg.norm(T["X"]["yawpitch"][i] - T["X"]["yawpitch"][f["still"]].mean(0), axis=1)
        i = i[turn < reach]
        if len(i) < 10:
            continue
        for n in rows:
            rows[n].append(T["X"][n][i] - T["X"][n][i].mean(0))
    if not rows["yawpitch"]:
        return None
    w = {n: np.concatenate(v) for n, v in rows.items()}
    return D.lstsq(w["yawpitch"], np.concatenate([w[n] for n in NAMES], 1))


def comp(T, K):
    ref = np.nanmean(S["X"]["yawpitch"][D.frames(pool)[0]], 0)
    return D.cols(T, NAMES) - (T["X"]["yawpitch"] - ref) @ K


def score(x, train, key="i"):
    i, y = D.frames(train, key)
    p = D.fit(x[i], y, lam=0.0)
    return [med(D.offsets(x, t, p)[1]) for t in tests.values()]


K_prof = slopes(H, hfix)  # "profile" slopes: the re-record, all 10 fixations, 4 s
x_prof = comp(S, K_prof)
print("\nprofile slopes (re-record, 10 x 4 s): eye_x/yaw %.3f, eye_y/pitch %.3f" % (K_prof[0, 0], K_prof[1, 1]))

# 1. how few static fixations, slopes given by the profile
print("\n1. static fixations needed, slopes from the profile. median deg [early, late]; random subsets: median (p10-p90)")
grid = {tuple(f["cell"]): f for f in pool}
named = {
    "5: corners + centre": [(0, 0), (4, 0), (0, 4), (4, 4), (2, 2)],
    "9: outer 3x3": [(a, b) for a in (0, 2, 4) for b in (0, 2, 4)],
}
for n, cells in named.items():
    print(f"  {n:<24}", np.round(score(x_prof, [grid[c] for c in cells]), 2))
print(f"  {'10: budget (pilot)':<24}", np.round(score(x_prof, D.budget(pool)), 2))
print(f"  {'25: whole pool':<24}", np.round(score(x_prof, pool), 2))
for n in (4, 5, 6, 7, 8, 9, 10):
    r = np.array([score(x_prof, [pool[j] for j in rng.choice(25, n, replace=False)]) for _ in range(300)])
    q = np.percentile(r, [50, 10, 90], 0).round(2)
    print(f"  random {n:<2}  early {q[0,0]} ({q[1,0]}-{q[2,0]})  late {q[0,1]} ({q[1,1]}-{q[2,1]})")

# 2. how many head-held fixations and how long, for the slopes (re-record), map from the pilot's 10
print("\n2. slopes from k head-held fixations held dur s (re-record); map from 10 static. median over subsets (p10-p90)")
p10 = D.budget(pool)
for dur in (1.0, 2.0, 4.0):
    for k in (1, 2, 3, 4, 6, 10):
        subs = list(combinations(range(len(hfix)), k))
        if len(subs) > 120:
            subs = [subs[j] for j in rng.choice(len(subs), 120, replace=False)]
        r, kx = [], []
        for s in subs:
            K = slopes(H, [hfix[j] for j in s], dur)
            if K is None:
                continue
            r.append(score(comp(S, K), p10))
            kx.append(K[0, 0])
        r = np.array(r)
        q = np.percentile(r, [50, 10, 90], 0).round(2)
        print(f"  dur {dur:.0f} s k {k:<2} n={len(r):<3} early {q[0,0]} ({q[1,0]}-{q[2,0]})  late {q[0,1]} ({q[1,1]}-{q[2,1]})  eye_x/yaw {np.median(kx):.3f} sd {np.std(kx):.3f}")
print("  no compensation:", np.round(score(D.cols(S, NAMES), p10), 2))

# 3. every calibration fixation head-held: map and slopes from the session's own head block (last in session: not causal)
print("\n3. map AND slopes from k of the session's head-block fixations (first dur s after the press), nothing static")
for dur in (2.0, 4.0):
    for k in (4, 5, 6, 7, 10):
        subs = list(combinations(range(len(head)), k))
        if len(subs) > 120:
            subs = [subs[j] for j in rng.choice(len(subs), 120, replace=False)]
        r = []
        for s in subs:
            fx = [head[j] for j in s]
            K = slopes(S, fx, dur)
            if K is None:
                continue
            x = comp(S, K)
            tr = []
            for f in fx:
                i = f["moving"][: int(dur * 30)]
                turn = np.linalg.norm(S["X"]["yawpitch"][i] - S["X"]["yawpitch"][f["still"]].mean(0), axis=1)
                tr.append({**f, "i": i[turn < 6]})
            tr = [f for f in tr if len(f["i"]) >= 10]
            if len(tr) < 4:
                continue
            r.append(score(x, tr))
        r = np.array(r)
        q = np.percentile(r, [50, 10, 90], 0).round(2)
        c = np.mean([cost(f, dur) for f in head])
        print(f"  dur {dur:.0f} s k {k:<2} (~{k*c:.0f} s) n={len(r):<3} early {q[0,0]} ({q[1,0]}-{q[2,0]})  late {q[0,1]} ({q[1,1]}-{q[2,1]})")

# 4. mixed: n static (budget order) + slopes from k session head-block fixations, within 30 s
print("\n4. mixed within 30 s: n static (outer first) + k head-held from the session's head block, 4 s and 2 s holds")
order = sorted(pool, key=lambda f: not (f["cell"][0] in (0, 2, 4) and f["cell"][1] in (0, 2, 4)))
cs = np.mean([cost(f, 31 / 30) for f in pool])
for dur in (4.0, 2.0):
    ch = np.mean([cost(f, dur) for f in head])
    for k in (1, 2, 3):
        n = int((30 - k * ch) // cs)
        subs = list(combinations(range(len(head)), k))
        r = np.array([score(comp(S, K), order[:n]) for s in subs if (K := slopes(S, [head[j] for j in s], dur)) is not None])
        q = np.percentile(r, [50, 10, 90], 0).round(2)
        print(f"  hold {dur:.0f} s: {n} static + {k} head-held (~{n*cs+k*ch:.0f} s)  early {q[0,0]} ({q[1,0]}-{q[2,0]})  late {q[0,1]} ({q[1,1]}-{q[2,1]})")
