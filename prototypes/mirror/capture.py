"""PROTOTYPE, throwaway. Built-in camera via PyObjC: luma frames with host-clock stamps, arrival times and driver metadata."""

import queue
import time

import AVFoundation as AVF
import CoreMedia as CM
import Quartz
import libdispatch
import numpy as np
import objc
from Foundation import NSObject

DELIVER = "com.apple.cmio.buffer_attachment.deliver_time"


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


def _attachment(sb, key):
    r = CM.CMGetAttachment(sb, key, None)
    return r[0] if isinstance(r, tuple) else r


class _Sink(NSObject):
    def initWithQueue_(self, q):
        self = objc.super(_Sink, self).init()
        self.q, self.drops = q, 0
        return self

    def captureOutput_didOutputSampleBuffer_fromConnection_(self, out, sb, conn):
        try:
            arrival = time.monotonic()
            t = CM.CMSampleBufferGetPresentationTimeStamp(sb)
            meta = {}
            md = _attachment(sb, "MetadataDictionary")  # undocumented driver metadata
            if md is not None:
                meta = {"exposure_s": float(md.get("ExposureTime", 0)), "skew_us": int(md.get("RollingShutterSkew", 0))}
            dt = _attachment(sb, DELIVER)
            if dt is not None:
                meta["deliver_s"] = int(dt["value"]) / int(dt["timescale"])
            pb = CM.CMSampleBufferGetImageBuffer(sb)
            Quartz.CVPixelBufferLockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
            h = Quartz.CVPixelBufferGetHeightOfPlane(pb, 0)
            w = Quartz.CVPixelBufferGetWidthOfPlane(pb, 0)
            r = Quartz.CVPixelBufferGetBytesPerRowOfPlane(pb, 0)
            base = Quartz.CVPixelBufferGetBaseAddressOfPlane(pb, 0)
            y = np.frombuffer(base.as_buffer(r * h), np.uint8).reshape(h, r)[:, :w].copy()
            Quartz.CVPixelBufferUnlockBaseAddress(pb, Quartz.kCVPixelBufferLock_ReadOnly)
            self.q.put((t.value / t.timescale, arrival, meta, y))
        except Exception as e:  # an exception escaping a PyObjC callback crashes the process
            print("sink:", e)

    def captureOutput_didDropSampleBuffer_fromConnection_(self, out, sb, conn):
        self.drops += 1


class Camera:
    """Fixed format, 30 fps pinned, Center Stage forced off. Frames arrive on `self.q` as (pts_s, arrival_s, meta, luma)."""

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
            "drops": self.sink.drops,
        }
