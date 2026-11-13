"""PROTOTYPE, throwaway. Built-in camera via PyObjC: native 420v frames, host-clock timestamps."""

import queue

import AVFoundation as AVF
import CoreMedia as CM
import Quartz
import libdispatch
import numpy as np
import objc
from Foundation import NSObject


def device():
    return AVF.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        [AVF.AVCaptureDeviceTypeBuiltInWideAngleCamera], AVF.AVMediaTypeVideo, AVF.AVCaptureDevicePositionUnspecified
    ).devices()[0]


def formats(dev):
    out = {}
    for f in dev.formats():
        d = CM.CMVideoFormatDescriptionGetDimensions(f.formatDescription())
        out[(d.width, d.height)] = f
    return out


class _Sink(NSObject):
    def initWithQueue_(self, q):
        self = objc.super(_Sink, self).init()
        self.q, self.drops = q, 0
        return self

    def captureOutput_didOutputSampleBuffer_fromConnection_(self, out, sb, conn):
        try:
            t = CM.CMSampleBufferGetPresentationTimeStamp(sb)
            pb = CM.CMSampleBufferGetImageBuffer(sb)
            Quartz.CVPixelBufferLockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
            planes = []
            for i in (0, 1):
                h = Quartz.CVPixelBufferGetHeightOfPlane(pb, i)
                w = Quartz.CVPixelBufferGetWidthOfPlane(pb, i) * (i + 1)
                r = Quartz.CVPixelBufferGetBytesPerRowOfPlane(pb, i)
                base = Quartz.CVPixelBufferGetBaseAddressOfPlane(pb, i)
                a = np.frombuffer(base.as_buffer(r * h), np.uint8).reshape(h, r)
                planes.append(a[:, :w].copy())
            Quartz.CVPixelBufferUnlockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
            self.q.put((t.value / t.timescale, np.vstack(planes)))  # NV12, video range
        except Exception as e:  # an exception escaping a PyObjC callback crashes the process
            print("sink:", e)

    def captureOutput_didDropSampleBuffer_fromConnection_(self, out, sb, conn):
        self.drops += 1


class Camera:
    """Fixed format, 30 fps pinned, Center Stage forced off. Frames arrive on `self.q` as (pts_s, nv12)."""

    def __init__(self, size):
        self.q = queue.Queue()
        self.dev = dev = device()
        AVF.AVCaptureDevice.setCenterStageControlMode_(AVF.AVCaptureCenterStageControlModeApp)
        AVF.AVCaptureDevice.setCenterStageEnabled_(False)
        self.session = s = AVF.AVCaptureSession.alloc().init()
        s.beginConfiguration()
        inp, err = AVF.AVCaptureDeviceInput.deviceInputWithDevice_error_(dev, None)
        assert inp, err
        s.addInput_(inp)
        out = AVF.AVCaptureVideoDataOutput.alloc().init()
        out.setVideoSettings_({
            Quartz.kCVPixelBufferPixelFormatTypeKey: Quartz.kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange
        })
        self.sink = _Sink.alloc().initWithQueue_(self.q)
        out.setSampleBufferDelegate_queue_(self.sink, libdispatch.dispatch_queue_create(b"cam", None))
        s.addOutput_(out)
        s.commitConfiguration()
        self.size = size

    def _configure(self, size):
        ok, err = self.dev.lockForConfiguration_(None)
        assert ok, err
        self.dev.setActiveFormat_(formats(self.dev)[size])
        d = CM.CMTimeMake(1, 30)
        self.dev.setActiveVideoMinFrameDuration_(d)
        self.dev.setActiveVideoMaxFrameDuration_(d)
        self.dev.unlockForConfiguration()

    def start(self):
        self.session.startRunning()
        self._configure(self.size)  # set before start, the session preset overrides it
        return self

    def stop(self):
        self.session.stopRunning()

    def state(self):
        d = self.dev
        f = CM.CMVideoFormatDescriptionGetDimensions(d.activeFormat().formatDescription())
        lo, hi = d.activeVideoMinFrameDuration(), d.activeVideoMaxFrameDuration()
        return {
            "format": [f.width, f.height],
            "frame_duration_s": [lo.value / lo.timescale, hi.value / hi.timescale],
            "center_stage_active": bool(d.isCenterStageActive()),
            "portrait_active": bool(d.isPortraitEffectActive()),
            "studio_light_active": bool(d.isStudioLightActive()),
            "drops": self.sink.drops,
        }


if __name__ == "__main__":  # smoke test: one second of frames
    import time

    cam = Camera((1920, 1080)).start()
    time.sleep(1.5)
    cam.stop()
    pts = []
    while not cam.q.empty():
        t, f = cam.q.get()
        pts.append(t)
    print(cam.dev.localizedName(), cam.state(), len(pts), f.shape, "dt_ms", np.diff(pts).round(4) * 1000)
