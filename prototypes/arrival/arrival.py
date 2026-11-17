# /// script
# requires-python = ">=3.13"
# dependencies = ["numpy", "pyobjc-framework-AVFoundation", "pyobjc-framework-libdispatch", "pyobjc-framework-Quartz", "pyobjc-framework-Cocoa"]
# ///
"""PROTOTYPE, throwaway. Why does a frame arrive 80 ms after its stamp, and can that be cut? (#25)

  uv run arrival.py probe            # formats, frame rates, device state, one frame's attachments
  uv run arrival.py sweep [n] [quick]  # the delay per setting, n short captures each, interleaved
  uv run arrival.py live             # 60 s, a line per half second: change the light and watch the delay
                                     #   `hud` after sweep or live floats the readout on screen
  uv run arrival.py long             # one long capture: the delay against time since start
  uv run arrival.py one k=v ...      # one capture of a named setting, e.g. one size=1280x720 fps=15 s=20
                                     #   app=1 runs it under a Cocoa app, app=2 adds a full-screen white window (app=3 black),
                                     #   spin=1 adds a busy Python thread
  uv run arrival.py report           # re-print every file in results/

Delay is a frame's arrival in the Python callback (host clock) minus its stamp (presentation time,
host clock). The driver's own deliver time, an undocumented attachment, splits it: stamp to deliver
is the camera, deliver to arrival is AVFoundation and Python. No frames are kept.

Found (2026-11-16, results/): the delay is the camera's. It has two states, read per frame from the
driver's undocumented metadata. Slow, about 17 ms later, is `MachineLearningVideoNoiseReductionApplied`
(with `TemporalNoiseReductionBand0Strength` 0 and a second exposure attached): the light is low enough
for the gain to sit at its 8x limit at 16.7 ms exposure. No format or frame rate leaves it.
"""

import json
import platform
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import AVFoundation as AVF
import CoreMedia as CM
import Quartz
import libdispatch
import numpy as np
import objc
from Foundation import NSObject

RESULTS = Path(__file__).parent / "results"
DELIVER = "com.apple.cmio.buffer_attachment.deliver_time"
PIX = {
    "420v": Quartz.kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
    "420f": Quartz.kCVPixelFormatType_420YpCbCr8BiPlanarFullRange,
    "BGRA": Quartz.kCVPixelFormatType_32BGRA,
    "2vuy": Quartz.kCVPixelFormatType_422YpCbCr8,
    "native": None,
}
# per-frame columns; the driver metadata keys are undocumented
COLS = ["pts", "arrival", "deliver", "exposure", "luma", "done", "hosttime", "opts", "sifr_exposure", "sifr_opts",
        "lux", "agc", "mstf", "tnr", "skew", "hdr_ratio", "fps_now", "ae_stable", "width", "mlvnr"]
I = {n: i for i, n in enumerate(COLS)}
CLOCK = ["pts", "arrival", "deliver", "done", "hosttime", "opts", "sifr_opts"]
BASE = dict(size="1920x1080", fps=30, pix="420v", discard=True, stage=False, copy=True, when="after", preset=None, s=8)


def fourcc(n):
    return bytes([(n >> 24) & 255, (n >> 16) & 255, (n >> 8) & 255, n & 255]).decode("latin1")


def device():
    return AVF.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        [AVF.AVCaptureDeviceTypeBuiltInWideAngleCamera], AVF.AVMediaTypeVideo, AVF.AVCaptureDevicePositionUnspecified
    ).devices()[0]


def dims(f):
    d = CM.CMVideoFormatDescriptionGetDimensions(f.formatDescription())
    return d.width, d.height


def formats(dev):
    return {"%dx%d" % dims(f): f for f in dev.formats()}


def _attachment(sb, key):
    r = CM.CMGetAttachment(sb, key, None)
    return r[0] if isinstance(r, tuple) else r


def _secs(t):
    return t.value / t.timescale


def effects(dev):
    out = {}
    for name in ("isCenterStageActive", "isPortraitEffectActive", "isStudioLightActive", "isBackgroundReplacementActive",
                 "canPerformReactionEffects", "isVideoHDREnabled", "isContinuityCamera", "isSuspended"):
        if dev.respondsToSelector_(name):
            out[name] = bool(getattr(dev, name)())
    for name in ("isCenterStageEnabled", "isPortraitEffectEnabled", "isStudioLightEnabled", "reactionEffectsEnabled",
                 "reactionEffectGesturesEnabled", "isBackgroundReplacementEnabled"):
        if AVF.AVCaptureDevice.respondsToSelector_(name):
            out["class." + name] = bool(getattr(AVF.AVCaptureDevice, name)())
    return out


class _Sink(NSObject):
    def initWithCopy_(self, copy):
        self = objc.super(_Sink, self).init()
        self.rows, self.drops, self.copy, self.first, self.shape, self.snap = [], 0, copy, None, None, {}
        return self

    def captureOutput_didOutputSampleBuffer_fromConnection_(self, out, sb, conn):
        try:
            arrival = time.monotonic()
            pts = _secs(CM.CMSampleBufferGetPresentationTimeStamp(sb))
            md = _attachment(sb, "MetadataDictionary") or {}
            num = lambda d, k: float(d[k]) if d.get(k) is not None else float("nan")
            cmt = lambda d: int(d["value"]) / int(d["timescale"]) if d is not None else float("nan")
            exposure = num(md, "ExposureTime")
            deliver = cmt(_attachment(sb, DELIVER))
            host = _attachment(sb, "com.apple.cmio.buffer_attachment.hosttime")
            sifr = md.get("SIFRMetadata") or {}
            luma = float("nan")
            key = f"second exposure {'on' if sifr else 'off'}, tnr {md.get('TemporalNoiseReductionBand0Strength')}"
            if len(self.rows) > 45 and key not in self.snap:  # the driver's scalar metadata, once per state, to compare states
                self.snap[key] = {str(k): float(v) for k, v in md.items() if isinstance(v, (int, float))}
            pb = CM.CMSampleBufferGetImageBuffer(sb)
            if self.shape is None:
                self.shape = [Quartz.CVPixelBufferGetWidth(pb), Quartz.CVPixelBufferGetHeight(pb),
                              fourcc(Quartz.CVPixelBufferGetPixelFormatType(pb))]
            if self.first is None:
                self.first = sb
            if self.copy:  # what a pipeline must do at least: own the pixels
                Quartz.CVPixelBufferLockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
                planar = Quartz.CVPixelBufferIsPlanar(pb)
                h = Quartz.CVPixelBufferGetHeightOfPlane(pb, 0) if planar else Quartz.CVPixelBufferGetHeight(pb)
                r = Quartz.CVPixelBufferGetBytesPerRowOfPlane(pb, 0) if planar else Quartz.CVPixelBufferGetBytesPerRow(pb)
                base = Quartz.CVPixelBufferGetBaseAddressOfPlane(pb, 0) if planar else Quartz.CVPixelBufferGetBaseAddress(pb)
                y = np.frombuffer(base.as_buffer(r * h), np.uint8).copy()
                Quartz.CVPixelBufferUnlockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
                luma = float(y[::97].mean())
            self.rows.append((pts, arrival, deliver, exposure, luma, time.monotonic(),
                              int(host) / 1e9 if host is not None else float("nan"), cmt(md.get("OriginalPresentationTimeStamp")),
                              num(sifr, "ExposureTime"), cmt(sifr.get("OriginalPresentationTimeStamp")),
                              num(md, "LuxLevel"), num(md, "AGC"), num(md, "MSTFCurrentEnabled"),
                              num(md, "TemporalNoiseReductionBand0Strength"), num(md, "RollingShutterSkew"),
                              num(md, "HDRExposureRatio"), num(md, "CurrentFrameRate"), num(md, "AEStable"),
                              Quartz.CVPixelBufferGetWidth(pb), num(md, "MachineLearningVideoNoiseReductionApplied")))
        except Exception as e:  # an exception escaping a PyObjC callback crashes the process
            print("sink:", e)

    def captureOutput_didDropSampleBuffer_fromConnection_(self, out, sb, conn):
        self.drops += 1


def capture(c):
    """One capture of setting `c`. Returns the per-frame rows and the state the device reported."""
    c = BASE | c
    dev = device()
    AVF.AVCaptureDevice.setCenterStageControlMode_(AVF.AVCaptureCenterStageControlModeApp)
    AVF.AVCaptureDevice.setCenterStageEnabled_(bool(c["stage"]))
    s = AVF.AVCaptureSession.alloc().init()
    s.beginConfiguration()
    if c["preset"]:
        s.setSessionPreset_(getattr(AVF, "AVCaptureSessionPreset" + c["preset"]))
    inp, err = AVF.AVCaptureDeviceInput.deviceInputWithDevice_error_(dev, None)
    assert inp, err
    s.addInput_(inp)
    out = AVF.AVCaptureVideoDataOutput.alloc().init()
    if PIX[c["pix"]] is not None:
        out.setVideoSettings_({Quartz.kCVPixelBufferPixelFormatTypeKey: PIX[c["pix"]]})
    else:
        out.setVideoSettings_({})
    out.setAlwaysDiscardsLateVideoFrames_(bool(c["discard"]))
    sink = _Sink.alloc().initWithCopy_(bool(c["copy"]))
    out.setSampleBufferDelegate_queue_(sink, libdispatch.dispatch_queue_create(b"cam", None))
    s.addOutput_(out)
    s.commitConfiguration()

    def configure():
        ok, err = dev.lockForConfiguration_(None)
        assert ok, err
        dev.setActiveFormat_(formats(dev)[c["size"]])
        d = CM.CMTimeMake(1, int(c["fps"]))
        dev.setActiveVideoMinFrameDuration_(d)
        dev.setActiveVideoMaxFrameDuration_(d)
        dev.unlockForConfiguration()

    t0 = time.monotonic()
    if c["preset"]:
        s.startRunning()
    elif c["when"] == "after":  # as the mirror loop did: the session preset overrides a format set before start
        s.startRunning()
        configure()
    else:  # hold the device lock across start, so the session leaves the format alone
        ok, err = dev.lockForConfiguration_(None)
        assert ok, err
        configure()
        s.startRunning()
        dev.unlockForConfiguration()
    started = time.monotonic()
    seen = 0
    while time.monotonic() - started < float(c["s"]):  # a line per half second, for changing the light while watching
        time.sleep(0.5)
        r = np.array(sink.rows[seen:], float).reshape(-1, len(COLS))
        seen += len(r)
        if len(r) and (c.get("live") or HUD):
            text = (f"arrival - stamp {1000 * np.median(r[:, 1] - r[:, 0]):5.1f} ms  exposure {1000 * np.median(r[:, 3]):4.1f} ms  "
                    f"second exposure {'on ' if np.isfinite(r[:, I['sifr_exposure']]).mean() > 0.5 else 'off'}  "
                    f"tnr {np.median(r[:, I['tnr']]):3.0f}  ml denoise {np.median(r[:, I['mlvnr']]):.0f}  lux {np.median(r[:, I['lux']]):5.0f}  gain {np.median(r[:, I['agc']]) / 256:4.1f}x")
            if c.get("live"):
                print(f"  {time.monotonic() - started:5.1f} s  {text}", flush=True)
            if HUD:
                band = (slow(r).mean() > 0.5)
                hud(("IN THE SLOW BAND, hold it" if band else "out of the band: aim for lux 300 to 1000") + f"   [{c.get('note', '')}]\n" + text)
    lo, hi = dev.activeVideoMinFrameDuration(), dev.activeVideoMaxFrameDuration()
    state = {
        "format": "%dx%d" % dims(dev.activeFormat()),
        "frame_duration_s": [_secs(lo), _secs(hi)],
        "buffer": sink.shape,
        "drops": sink.drops,
        "start_call_s": started - t0,
        "effects": effects(dev),
        "modes_while_running": {"exposure": [bool(dev.isExposureModeSupported_(m)) for m in range(4)],
                                "white_balance": [bool(dev.isWhiteBalanceModeSupported_(m)) for m in range(3)],
                                "focus": [bool(dev.isFocusModeSupported_(m)) for m in range(3)]},
        "snap": sink.snap,
    }
    s.stopRunning()
    rows = np.array(sink.rows, float).reshape(-1, len(COLS))
    rows[:, [I[n] for n in CLOCK]] -= t0  # seconds since the start call
    return rows, state, sink.first


HUD = None


def hud(text):
    from PyObjCTools import AppHelper
    AppHelper.callAfter(HUD.setStringValue_, text)


def slow(r):
    """The state the slow frames share: a second exposure attached and temporal noise reduction strength 0."""
    return np.isfinite(r[:, I["sifr_exposure"]]) & (r[:, I["tnr"]] == 0)


def by_state(rows, skip=1.0):
    """Deliver delay split by the camera's state, frame by frame."""
    r = rows[rows[:, 0] > rows[0, 0] + skip] if len(rows) else rows
    on = np.isfinite(r[:, I["sifr_exposure"]])
    out = {}
    for name, m in (("slow", slow(r)), ("second exposure, tnr 255", on & (r[:, I["tnr"]] != 0)), ("no second exposure", ~on)):
        if m.sum() >= 15:
            out[name] = {"frames": int(m.sum()), "deliver_ms": pct(1000 * (r[m, 2] - r[m, 0]), (5, 50, 95)),
                         "exposure_ms": pct(1000 * r[m, 3], (50,))[0], "lux": pct(r[m, I["lux"]], (5, 95))}
    return out


def pct(x, qs=(50, 95)):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return [round(float(np.percentile(x, q)), 1) for q in qs] if len(x) else [float("nan")] * len(qs)


def summary(rows, skip=2.0):
    """Steady state: frames stamped later than `skip` s after the first."""
    r = rows[rows[:, 0] > rows[0, 0] + skip] if len(rows) else rows
    if len(r) < 5:
        return {"frames": int(len(r))}
    period = np.diff(r[:, 0])
    return {
        "frames": int(len(r)),
        "fps": round(1 / float(np.median(period)), 2),
        "arrival_ms": pct(1000 * (r[:, 1] - r[:, 0]), (5, 50, 95)),
        "deliver_ms": pct(1000 * (r[:, 2] - r[:, 0]), (5, 50, 95)),
        "callback_ms": pct(1000 * (r[:, 5] - r[:, 1])),
        "exposure_ms": pct(1000 * r[:, 3], (5, 50, 95)),
        "luma": pct(r[:, 4], (50,))[0],
        "hosttime_ms": pct(1000 * (r[:, I["hosttime"]] - r[:, 0]), (50,))[0],
        "opts_ms": pct(1000 * (r[:, I["opts"]] - r[:, 0]), (50,))[0],
        "sifr": round(float(np.isfinite(r[:, I["sifr_exposure"]]).mean()), 2),
        "sifr_exposure_ms": pct(1000 * r[:, I["sifr_exposure"]], (50,))[0],
        "sifr_opts_ms": pct(1000 * (r[:, I["sifr_opts"]] - r[:, 0]), (50,))[0],
        "lux": pct(r[:, I["lux"]], (50,))[0],
        "agc": pct(r[:, I["agc"]], (50,))[0],
        "skew_ms": pct(r[:, I["skew"]] / 1000, (50,))[0],
        "first_frame_s": round(float(rows[0, 1]), 2),
    }


def line(name, sm, state):
    if "arrival_ms" not in sm:
        return f"{name:<34} no frames ({state.get('error', '')})"
    a, d, e = sm["arrival_ms"], sm["deliver_ms"], sm["exposure_ms"]
    return (f"{name:<34} {state['format']:>9} {sm['fps']:>5} fps  arrival {a[1]:>5} p95 {a[2]:>5}  deliver {d[1]:>5}  "
            f"cb {sm['callback_ms'][0]:>4}  exp {e[1]:>4}  sifr {sm['sifr']} {sm['sifr_exposure_ms']}  lux {sm['lux']:>5}  agc {sm['agc']:>5}  "
            f"skew {sm['skew_ms']}  host {sm['hosttime_ms']}  buf {state['buffer']}  drops {state['drops']}")


def save(kind, payload):
    RESULTS.mkdir(exist_ok=True)
    p = RESULTS / f"{datetime.now():%Y%m%d-%H%M%S}-{kind}.json"
    payload = {"kind": kind, "machine": platform.platform(), "base": BASE} | payload
    p.write_text(json.dumps(payload))
    print("saved", p)


def probe():
    dev = device()
    print(dev.localizedName(), dev.modelID(), "|", platform.platform())
    for f in dev.formats():
        desc = f.formatDescription()
        rates = [(r.minFrameRate(), r.maxFrameRate()) for r in f.videoSupportedFrameRateRanges()]
        extra = {n: bool(getattr(f, n)()) for n in ("isCenterStageSupported", "isPortraitEffectSupported", "isStudioLightSupported",
                                                     "isVideoHDRSupported", "isVideoBinned", "reactionEffectsSupported",
                                                     "isBackgroundReplacementSupported") if f.respondsToSelector_(n)}
        print(" ", "%dx%d" % dims(f), fourcc(CM.CMFormatDescriptionGetMediaSubType(desc)), rates,
              {k: v for k, v in extra.items() if v})
    print("effects:", effects(dev))
    print("exposure modes supported (locked, auto, continuous, custom):", [bool(dev.isExposureModeSupported_(m)) for m in range(4)],
          "| now", dev.exposureMode(), "| white balance (locked, auto, continuous):",
          [bool(dev.isWhiteBalanceModeSupported_(m)) for m in range(3)], "| focus:", [bool(dev.isFocusModeSupported_(m)) for m in range(3)])
    rows, state, sb = capture({"s": 2})
    print("state:", state)
    if "-v" in sys.argv:
        print("attachments:", CM.CMCopyDictionaryOfAttachments(None, sb, CM.kCMAttachmentMode_ShouldPropagate))
    print(line("base", summary(rows, 1.0), state))
    print("modes supported while running:", state["modes_while_running"])
    print("  per frame: arrival - stamp, exposure, sifr exposure, sifr stamp - stamp, hosttime - stamp, original stamp - stamp (ms)")
    for r in rows[:: max(1, len(rows) // 30)]:
        print("  ", (1000 * np.array([r[1] - r[0], r[3], r[I["sifr_exposure"]], r[I["sifr_opts"]] - r[0], r[I["hosttime"]] - r[0],
                                       r[I["opts"]] - r[0]])).round(1).tolist())


def parse(args):
    c = {}
    for a in args:
        k, v = a.split("=")
        c[k] = v if k in ("size", "pix", "when", "preset") else (v == "1" if k in ("discard", "stage", "copy", "live", "spin") else float(v))
    return c


def sweep(reps=2, quick=False):
    dev = device()
    conds = {"base": {}}
    for size in formats(dev):
        if size != BASE["size"]:
            conds[f"size {size}"] = {"size": size}
    rates = sorted({int(r.maxFrameRate()) for f in dev.formats() for r in f.videoSupportedFrameRateRanges()} | {15, 24, 30})
    lo = min(r.minFrameRate() for r in formats(dev)[BASE["size"]].videoSupportedFrameRateRanges())
    hi = max(r.maxFrameRate() for r in formats(dev)[BASE["size"]].videoSupportedFrameRateRanges())
    for fps in rates:
        if fps != BASE["fps"] and lo <= fps <= hi:
            conds[f"fps {fps}"] = {"fps": fps}
    for pix in PIX:
        if pix != BASE["pix"]:
            conds[f"pix {pix}"] = {"pix": pix}
    conds |= {
        "keep late frames": {"discard": False},
        "no pixel copy": {"copy": False},
        "format before start": {"when": "before"},
        "center stage on": {"stage": True},
        "preset 1920x1080": {"preset": "1920x1080"},
        "preset 1280x720": {"preset": "1280x720"},
        "preset 640x480": {"preset": "640x480"},
        "1280x720 fps 15": {"size": "1280x720", "fps": 15},
    }
    out = []
    if quick:  # the settings that change what the camera does, for a second scene
        conds = {n: c for n, c in conds.items() if not n.startswith(("pix", "keep", "no pixel", "format before", "preset"))}
    order = [n for _ in range(reps) for n in random.sample(list(conds), len(conds))]
    for i, name in enumerate(order):
        try:
            rows, state, _ = capture(conds[name] | {"note": f"{i + 1}/{len(order)} {name}"})
        except Exception as e:
            rows, state = np.zeros((0, len(COLS))), {"error": repr(e)}
        sm = summary(rows)
        print(f"[{i + 1}/{len(order)}]", line(name, sm, state), flush=True)
        bs = by_state(rows) if len(rows) else {}
        states(bs)
        out.append({"name": name, "cond": conds[name], "state": state, "summary": sm, "by_state": bs, "rows": rows.round(5).tolist()})
        time.sleep(1.0)
    save("sweep", {"captures": out})
    table(out)
    state_table(out)


def table(caps):
    names = list(dict.fromkeys(c["name"] for c in caps))
    print(f"\n{'setting':<24} {'arrival p50':>18} {'arrival p95':>18} {'deliver p50':>18} {'exposure p50':>16} {'second exp':>11}  got")
    for n in names:
        cs = [c for c in caps if c["name"] == n and "arrival_ms" in c["summary"]]
        if not cs:
            print(f"{n:<24} failed: {[c['state'].get('error') for c in caps if c['name'] == n][0]}")
            continue
        col = lambda key, i: " / ".join(f"{c['summary'][key][i]:.1f}" for c in cs)
        got = f"{cs[0]['state']['format']} {cs[0]['summary']['fps']} fps {cs[0]['state']['buffer'][2]}"
        print(f"{n:<24} {col('arrival_ms', 1):>18} {col('arrival_ms', 2):>18} {col('deliver_ms', 1):>18} {col('exposure_ms', 1):>16} {' / '.join(str(c['summary']['sifr']) for c in cs):>11}  {got}")


def state_table(caps):
    """Per setting and camera state: deliver delay p5 / p50 / p95 over the frames in that state, captures pooled."""
    print(f"\n{'setting':<24} {'slow: n  p5   p50   p95':>30} {'second exp, tnr 255':>30} {'no second exposure':>30}  width")
    for n in dict.fromkeys(c["name"] for c in caps):
        rows = [np.array(c["rows"]) for c in caps if c["name"] == n and c["rows"]]
        if not rows:
            continue
        r = np.concatenate([x[x[:, 0] > x[0, 0] + 1.0] for x in rows])
        bs = by_state(r, -1e9)
        cell = lambda k: (f"{bs[k]['frames']:>5} {bs[k]['deliver_ms'][0]:>5} {bs[k]['deliver_ms'][1]:>5} {bs[k]['deliver_ms'][2]:>5}"
                          if k in bs else "-")
        print(f"{n:<24} {cell('slow'):>30} {cell('second exposure, tnr 255'):>30} {cell('no second exposure'):>30}  "
              f"{int(np.median(r[:, I['width']]))} @ {1 / np.median(np.diff(rows[0][:, 0])):.0f} fps")


def over_time(rows, bin_s):
    print(f"  {'since start s':>14} {'arrival p50':>12} {'p95':>6} {'deliver p50':>12} {'exposure':>9} {'luma':>6} {'frames':>7} "
          f"{'sifr':>5} {'sifr exp':>8} {'lux':>5} {'agc':>5} {'ae ok':>5}")
    for t in np.arange(0, rows[-1, 0], bin_s):
        r = rows[(rows[:, 0] >= t) & (rows[:, 0] < t + bin_s)]
        if len(r):
            a = pct(1000 * (r[:, 1] - r[:, 0]))
            print(f"  {t:>14.1f} {a[0]:>12} {a[1]:>6} {pct(1000 * (r[:, 2] - r[:, 0]), (50,))[0]:>12} "
                  f"{pct(1000 * r[:, 3], (50,))[0]:>9} {pct(r[:, 4], (50,))[0]:>6} {len(r):>7} "
                  f"{np.isfinite(r[:, I['sifr_exposure']]).mean():>5.2f} {pct(1000 * r[:, I['sifr_exposure']], (50,))[0]:>8} "
                  f"{pct(r[:, I['lux']], (50,))[0]:>5} {pct(r[:, I['agc']], (50,))[0]:>5} {np.nanmean(r[:, I['ae_stable']]):>5.2f}")


def spinner():
    """A Python thread that holds the interpreter lock in 1 ms bursts, as a consumer thread would."""
    while True:
        x = 0
        for i in range(20000):
            x += i
        time.sleep(0.004)


def as_app(c, work):
    """Run `work` in a thread under a Cocoa app, as the mirror loop did: 1 the app alone, 2 with its full-screen white window."""
    import os
    import threading

    import AppKit
    from PyObjCTools import AppHelper

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    if c["app"] >= 2:
        frame = AppKit.NSScreen.mainScreen().frame()
        win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, AppKit.NSWindowStyleMaskBorderless, AppKit.NSBackingStoreBuffered, False)
        win.setLevel_(AppKit.NSMainMenuWindowLevel + 2)
        win.setBackgroundColor_(AppKit.NSColor.whiteColor() if c["app"] == 2 else AppKit.NSColor.blackColor())
        win.makeKeyAndOrderFront_(None)
        app.setPresentationOptions_(AppKit.NSApplicationPresentationHideDock | AppKit.NSApplicationPresentationHideMenuBar)
    if c.get("hud"):  # a small floating readout, so the light can be held where the slow frames are
        global HUD
        top = AppKit.NSScreen.mainScreen().frame().size.height
        panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((20, top - 130), (900, 70)), AppKit.NSWindowStyleMaskTitled | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered, False)
        panel.setTitle_("PROTOTYPE arrival: camera state")
        panel.setLevel_(AppKit.NSStatusWindowLevel)
        HUD = AppKit.NSTextField.labelWithString_("starting")
        HUD.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(13, 0))
        HUD.setFrame_(((10, 5), (880, 45)))
        panel.contentView().addSubview_(HUD)
        panel.orderFrontRegardless()
    else:
        app.activateIgnoringOtherApps_(True)

    def guarded():
        try:
            work()
        finally:
            sys.stdout.flush()
            os._exit(0)

    threading.Thread(target=guarded, daemon=True).start()
    AppHelper.runEventLoop()


def one(c, kind="one"):
    if c.get("spin"):
        import threading
        threading.Thread(target=spinner, daemon=True).start()
    if c.get("app"):
        app = c.pop("app")
        return as_app({"app": int(app)}, lambda: one(c | {"as_app": int(app)}, kind))
    rows, state, _ = capture(c)
    print(line(kind, summary(rows), state))
    states(by_state(rows), state["snap"])
    print("  first frames, arrival - stamp ms:", (1000 * (rows[:8, 1] - rows[:8, 0])).round(1).tolist())
    over_time(rows, max(0.5, rows[-1, 0] / 20))
    save(kind, {"captures": [{"name": kind, "cond": c, "state": state, "summary": summary(rows), "rows": rows.round(5).tolist()}]})


def states(bs, snap=None):
    for name, v in bs.items():
        print(f"  state {name:<26} frames {v['frames']:>5}  deliver - stamp p5 {v['deliver_ms'][0]:>5} p50 {v['deliver_ms'][1]:>5} "
              f"p95 {v['deliver_ms'][2]:>5}  exposure {v['exposure_ms']:>5}  lux {v['lux']}")
    if snap and len(snap) > 1:
        keys = sorted(set().union(*snap.values()))
        print("  driver metadata that differs between states:")
        for k in keys:
            vals = [v.get(k) for v in snap.values()]
            if len(set(vals)) > 1:
                print(f"    {k:<44}", "  |  ".join(f"{n}: {v.get(k)}" for n, v in snap.items()))


def report():
    for p in sorted(RESULTS.glob("*.json")):
        d = json.loads(p.read_text())
        print(f"\n== {p.name}")
        if d["kind"] == "sweep":
            table(d["captures"])
            if len(d["captures"][0]["rows"][0]) > I["width"]:
                state_table(d["captures"])
        else:
            for c in d["captures"]:
                print(line(c["name"] + " " + json.dumps(c["cond"]), c["summary"], c["state"]))
                over_time(np.array(c["rows"]), max(0.5, c["rows"][-1][0] / 20))


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else "probe"), sys.argv[2:]
    show = "hud" in args
    args = [a for a in args if a != "hud"]
    if cmd == "probe":
        probe()
    elif cmd == "sweep":
        work = lambda: sweep(next((int(a) for a in args if a.isdigit()), 2), "quick" in args)
        as_app({"app": 1, "hud": True}, work) if show else work()
    elif cmd == "live":
        work = lambda: one({"s": 60, "live": True} | parse(args), "live")
        as_app({"app": 1, "hud": True}, work) if show else work()
    elif cmd == "long":
        one({"s": 120} | parse(args), "long")
    elif cmd == "one":
        one(parse(args))
    elif cmd == "report":
        report()
