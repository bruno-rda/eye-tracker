# Built-in camera: what it delivers and how Python reaches it

Research for #5. Machine: MacBook Pro 14-inch, M4 Pro, model identifier Mac16,8, macOS 15.6 (24G84). Date: 2026-11-10.

Evidence labels:

- **[doc]**: stated by the linked primary source.
- **[observed]**: read on this machine through read-only AVFoundation queries (device and format enumeration, class properties). No capture session was started, no `AVCaptureDeviceInput` was created, no frame was captured. Method in the [appendix](#appendix-how-the-observed-values-were-read).
- **unverified**: not traced to a source and not observed. Treat as a hypothesis.

## Answer in brief

- Apple publishes three camera facts: "12MP Center Stage camera with support for Desk View", "1080p HD video recording", "Advanced image signal processor with computational video". No frame rate, field of view, aperture or sensor geometry. [doc: [tech specs](https://support.apple.com/en-us/121553)]
- The 12 MP sensor is not exposed. AVFoundation lists 7 formats, none above 1920 px in either dimension, all 15 to 30 fps, all `420v`. Largest by pixel count: 1552x1552 (2.41 MP). [observed]
- Field of view and intrinsics are not available from macOS APIs: `videoFieldOfView` and camera intrinsic matrix delivery are marked unavailable on macOS. Both must be measured. [doc: SDK headers, links below]
- Center Stage can be forced off from code (`centerStageControlMode = .app`, `isCenterStageEnabled = false`). Portrait, Studio Light, Background and Reactions are read-only to apps. Exposure, white balance and focus report no supported mode, so they cannot be locked through AVFoundation. [doc + observed]
- Frames carry a presentation timestamp on the session's synchronization clock. The macOS host time clock is `mach_absolute_time`, the same base as Python's `time.monotonic()`. No Apple source read here states a capture latency. [doc + observed]
- Two practical Python routes: OpenCV `CAP_AVFOUNDATION` (simple, no timestamps, no device controls, BGRA to BGR conversion and two copies per frame) and PyObjC with AVFoundation (full format, frame rate, timestamp and Center Stage control, at the cost of a Python callback on a dispatch queue).
- Camera permission is attributed to the app that launched the process (the terminal), not to Python. [doc: Apple DTS]

## Hardware and formats

Mac16,8 is "MacBook Pro (14-inch, 2024)" with M4 Pro or M4 Max. [doc: [Identify your MacBook Pro model](https://support.apple.com/en-us/108052)]

Published camera specification, complete: "12MP Center Stage camera with support for Desk View", "1080p HD video recording", "Advanced image signal processor with computational video". [doc: [tech specs](https://support.apple.com/en-us/121553)] The launch press release adds only "enhanced video quality in challenging lighting conditions". [doc: [Apple Newsroom, October 2024](https://www.apple.com/newsroom/2024/10/new-macbook-pro-features-m4-family-of-chips-and-apple-intelligence/)]

Sensor pixel dimensions, pixel pitch, lens focal length and aperture: unverified. No Apple source read here gives them.

### Devices [observed]

| Device type | Model ID | Formats |
|---|---|---|
| `builtInWideAngleCamera` | MacBook Pro Camera | 7 (below) |
| `deskViewCamera` | MacBook Pro Desk View Camera | 1: 1920x1440, 15 to 30 fps |
| `external` (Continuity Camera) | an iPhone | 8; listed while the phone is available as a Continuity Camera |

The Desk View camera is a separate virtual device: "a distortion-corrected cut out from an ultra wide camera". [doc: [deskViewCamera](https://developer.apple.com/documentation/avfoundation/avcapturedevice/devicetype-swift.struct/deskviewcamera)] That the built-in sensor sits behind an ultra wide lens follows from this plus the 0.5x/1x zoom control Apple describes for "a wide-angle camera" such as the 12MP Center Stage camera. [doc: [Use the camera on Mac, macOS 15](https://support.apple.com/guide/mac-help/use-the-camera-mchlp2980/15.0/mac/15.0)] The actual lens field of view is unverified.

### Formats of "MacBook Pro Camera" [observed]

| Dimensions (px) | Megapixels | Aspect | Frame rate range (fps) | Pixel format |
|---|---|---|---|---|
| 640x480 | 0.31 | 4:3 | 15 to 30 | `420v` |
| 1280x720 | 0.92 | 16:9 | 15 to 30 | `420v` |
| 1760x1328 | 2.34 | about 4:3 | 15 to 30 | `420v` |
| 1328x1760 | 2.34 | about 3:4 | 15 to 30 | `420v` |
| 1552x1552 | 2.41 | 1:1 | 15 to 30 | `420v` |
| 1920x1080 | 2.07 | 16:9 | 15 to 30 | `420v` |
| 1080x1920 | 2.07 | 9:16 | 15 to 30 | `420v` |

- No format exceeds 1920 px wide or 1920 px tall. There is no capture format above 1080p in width; the tallest are 1080x1920 and 1328x1760. [observed]
- Maximum frame rate is 30 fps for every format. One `AVFrameRateRange` per format. [observed]
- `420v` is 8-bit 4:2:0 bi-planar Y'CbCr, video range (luma 16 to 235). [doc: [kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange](https://developer.apple.com/documentation/corevideo/kcvpixelformattype_420ypcbcr8biplanarvideorange)] The luma plane is a ready grayscale image.
- With no session running, the device's active format was 1280x720, `activeVideoMinFrameDuration` 1/30 s, `activeVideoMaxFrameDuration` 1/15 s. [observed] The maximum frame duration is "the reciprocal of its minimum frame rate", so by default the device is allowed to drop to 15 fps. [doc: [activeVideoMaxFrameDuration](https://developer.apple.com/documentation/avfoundation/avcapturedevice/activevideomaxframeduration)] Whether it does so in low light is unverified.
- `isAutoVideoFrameRateSupported` is false for all 7 formats. [observed] That feature would otherwise switch 30 fps formats between 30 and 24 fps by light level. [doc: [isAutoVideoFrameRateEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/isautovideoframerateenabled)]
- Whether the 7 formats are crops or rescales of one another, and which gives the most pixels per degree, is unverified. It decides pixels per millimetre at the eye and must be measured.

Selecting a format: set `activeFormat`, `activeVideoMinFrameDuration` and `activeVideoMaxFrameDuration` under `lockForConfiguration()`, inside `beginConfiguration()`/`commitConfiguration()`. Frame durations outside the format's `videoSupportedFrameRateRanges` raise an exception. [doc: [activeFormat](https://developer.apple.com/documentation/avfoundation/avcapturedevice/activeformat), [activeVideoMinFrameDuration](https://developer.apple.com/documentation/avfoundation/avcapturedevice/activevideominframeduration)]

## Field of view and intrinsics

- `AVCaptureDevice.Format.videoFieldOfView` is `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h` in the macOS 15.5 SDK; the [documentation page](https://developer.apple.com/documentation/avfoundation/avcapturedevice/format/videofieldofview) lists no macOS availability] Compiling a read of it for macOS fails with "'videoFieldOfView' is unavailable in macOS". [observed]
- `AVCaptureConnection.isCameraIntrinsicMatrixDeliverySupported` and `isCameraIntrinsicMatrixDeliveryEnabled` are `API_UNAVAILABLE(macos)`. [doc: `AVCaptureSession.h` in the macOS 15.5 SDK; [documentation page](https://developer.apple.com/documentation/avfoundation/avcaptureconnection/iscameraintrinsicmatrixdeliverysupported) lists no macOS availability]
- Geometric distortion correction control (`isGeometricDistortionCorrectionEnabled`), `videoZoomFactor`, `isVideoBinned` are `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h`, macOS 15.5 SDK]
- Whether the delivered frames are already distortion-corrected by the system is unverified.
- Apple publishes no field of view for this camera. [doc: [tech specs](https://support.apple.com/en-us/121553) contain none]

Consequence: horizontal field of view, focal length in pixels, principal point and distortion must come from calibration on the machine, per format. Under a pinhole model the pixel density at the eye is `W / (2 d tan(HFOV/2))` px/mm for frame width `W` px and distance `d` mm; `HFOV` is the unknown.

## Processing applied by macOS

SDK header paths below are relative to `/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk/System/Library/Frameworks/AVFoundation.framework/Headers/`.

| Processing | State on this machine [observed] | Control from code |
|---|---|---|
| Center Stage | control mode `user`, enabled false, active false; all 7 formats support it, zoom range 1.0 to 1.0, 15 to 30 fps | Yes. Set `AVCaptureDevice.centerStageControlMode = .app`, then `isCenterStageEnabled = false`. In `.app` mode "the system disallows user control through Control Center". Setting enabled while in `.user` mode throws. [doc: [.app](https://developer.apple.com/documentation/avfoundation/avcapturedevice/centerstagecontrolmode-swift.enum/app), [isCenterStageEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/iscenterstageenabled)] |
| Manual framing (zoom 0.5x/1x, pan, recenter) | not readable | No API found. User control in the menu bar Video menu when Center Stage is off. [doc: [Use the camera on Mac](https://support.apple.com/guide/mac-help/use-the-camera-mchlp2980/15.0/mac/15.0)] Whether it changes the frames a third-party process receives is unverified. |
| Desk View | separate device | Not applied to the main camera stream; it is its own `deskViewCamera` device. [doc: [deskViewCamera](https://developer.apple.com/documentation/avfoundation/avcapturedevice/devicetype-swift.struct/deskviewcamera)] |
| Portrait (background blur) | enabled false, active false; all formats support it | No. `isPortraitEffectEnabled` is get-only: "whether the user enabled the Portrait video effect in Control Center". [doc: [isPortraitEffectEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/isportraiteffectenabled)] |
| Studio Light | enabled false, active false; all formats support it | No. Get-only. "the system artificially lights the subject's face". [doc: [isStudioLightEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/isstudiolightenabled)] |
| Background replacement | enabled false, active false | No. Get-only. [doc: [isBackgroundReplacementEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/isbackgroundreplacementenabled)] |
| Reactions | `reactionEffectsEnabled` true, `reactionEffectGesturesEnabled` false | No. Both get-only. "In macOS, the system enables reaction effects for all apps by default." Gesture triggering follows the Gestures toggle in Control Center. [doc: [reactionEffectsEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/reactioneffectsenabled), [reactionEffectGesturesEnabled](https://developer.apple.com/documentation/avfoundation/avcapturedevice/reactioneffectgesturesenabled)] |
| Auto exposure | `isExposureModeSupported` false for locked, autoExpose, continuousAutoExposure, custom | No. No mode can be set. Custom duration and ISO (`setExposureModeCustom`, `exposureDuration`, `ISO`, `exposureTargetBias`) are `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h`; [setExposureModeCustom](https://developer.apple.com/documentation/avfoundation/avcapturedevice/setexposuremodecustom(duration:iso:completionhandler:)) lists no macOS] |
| Auto white balance | `isWhiteBalanceModeSupported` false for locked, auto, continuous | No. Gain locking (`setWhiteBalanceModeLocked(with:)`, `deviceWhiteBalanceGains`) is `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h`] |
| Focus | `isFocusModeSupported` false for all modes | No. Lens position API is `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h`] Fixed focus is the likely reason; unverified. |
| Denoising, tone mapping, "computational video" | not readable | No API found in `AVCaptureDevice.h`. Low light boost and video HDR properties are `API_UNAVAILABLE(macos)`. [doc: `AVCaptureDevice.h`] What the ISP does to the frames is unverified. |
| Frame rate by light level | min 1/30 s, max 1/15 s frame duration by default | Yes. Set both frame durations to 1/30 s to pin 30 fps. [doc: [activeVideoMaxFrameDuration](https://developer.apple.com/documentation/avfoundation/avcapturedevice/activevideomaxframeduration)] |

Notes:

- The support flags were read with no session running. Whether exposure or white balance modes become supported once a session runs is unverified.
- The effect toggles are user state in the Video menu. An app can open that UI with `AVCaptureDevice.showSystemUserInterface(.videoEffects)` and read `isCenterStageActive`, `isPortraitEffectActive`, `isStudioLightActive`, `isBackgroundReplacementActive`, `reactionEffectsInProgress`. [doc: [showSystemUserInterface](https://developer.apple.com/documentation/avfoundation/avcapturedevice/showsystemuserinterface(_:)), [isCenterStageActive](https://developer.apple.com/documentation/avfoundation/avcapturedevice/iscenterstageactive)] A recorder should assert these are false at start and log them.
- Whether effect state is per app or global is unverified. The values above were read from a `swift` script and a `python` process, not from the eventual capture process.
- When Center Stage is active "the camera automatically pans, tightens, or widens the field of view", which changes the mapping from pixels to angles frame by frame. [doc: [isCenterStageActive](https://developer.apple.com/documentation/avfoundation/avcapturedevice/iscenterstageactive)] It must be off for gaze work.

## Timestamps and latency

- Each frame arrives as a `CMSampleBuffer` in `captureOutput(_:didOutput:from:)` on the dispatch queue given to `setSampleBufferDelegate(_:queue:)`. [doc: [captureOutput(_:didOutput:from:)](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutputsamplebufferdelegate/captureoutput(_:didoutput:from:))]
- "All capture output sample buffer timestamps are on the synchronization clock's timebase." `AVCaptureSession.synchronizationClock` (macOS 12.3+) is that clock; `AVCaptureInput.Port.clock` is the device clock, and `CMSyncConvertTime` converts between them. [doc: [synchronizationClock](https://developer.apple.com/documentation/avfoundation/avcapturesession/synchronizationclock)]
- "In macOS, the host time clock uses `mach_absolute_time`". [doc: [CMClockGetHostTimeClock](https://developer.apple.com/documentation/coremedia/cmclockgethosttimeclock())] Python's `time.monotonic()` reports implementation `mach_absolute_time()`, and `CMClockGetTime(CMClockGetHostTimeClock())` agreed with `time.monotonic()` within 1 microsecond in 3 consecutive reads (Python 3.13.13, PyObjC 13.0, this machine). [observed]
- That the session's synchronization clock is the host time clock for this camera is unverified. If it is, `time.monotonic() - PTS` at the callback is the capture-to-callback delay with no conversion.
- Which instant of the exposure the timestamp marks (start, middle, end of readout) is unverified.
- Late frames: with `alwaysDiscardsLateVideoFrames` true (the default) the output discards frames captured while the delegate queue is blocked. [doc: [alwaysDiscardsLateVideoFrames](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutput/alwaysdiscardslatevideoframes)] Each drop is reported to `captureOutput(_:didDrop:from:)` with a reason attachment (`FrameWasLate`, `OutOfBuffers`, `Discontinuity`). [doc: [captureOutput(_:didDrop:from:)](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutputsamplebufferdelegate/captureoutput(_:diddrop:from:))] "Process every frame" is therefore checkable only on a route that exposes this callback.
- Holding sample buffers too long starves the capture buffer pool and causes drops; copy the data and release. [doc: [captureOutput(_:didOutput:from:)](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutputsamplebufferdelegate/captureoutput(_:didoutput:from:))]
- Capture latency (light on sensor to callback): no figure in any source read for this ticket. Unverified whether Apple documents one. Known bound from the formats: frame period is 33.3 ms at 30 fps, so a 100 ms budget is 3 frame periods.

## Routes from Python

| | OpenCV `CAP_AVFOUNDATION` | PyObjC + AVFoundation | FFmpeg `avfoundation` device (CLI, PyAV, OpenCV `CAP_FFMPEG`) |
|---|---|---|---|
| Version read | opencv 5.0.0 source; opencv-python-headless 5.0.0 wheel | pyobjc 13.0 | FFmpeg n9.0.1 source and docs |
| Format selection | Width and height only, via output `videoSettings`; result not guaranteed native | Any `AVCaptureDevice.Format`, set as `activeFormat` | `-video_size`, `-pixel_format`; sets `activeFormat` |
| Frame rate selection | `CAP_PROP_FPS`: snaps to the maximum of the nearest range (30 fps here) | `activeVideoMinFrameDuration`/`MaxFrameDuration`, 15 to 30 fps | `-framerate`, default 30000/1001 |
| Capture timestamp | Not exposed | `CMSampleBufferGetPresentationTimeStamp` | Packet pts from sample buffer timing |
| Device controls | None | Center Stage control mode and enable; read effect state | None |
| Drop reporting | None | `didDrop` callback | None; `-drop_late_frames` default true |
| Pixel format delivered | BGR, converted from BGRA | Native `420v`, or any type the output offers | `-pixel_format`, default yuv420p |

### OpenCV, AVFoundation backend

Source: [`modules/videoio/src/cap_avfoundation_mac.mm` at tag 5.0.0](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm). The PyPI wheel `opencv-python-headless` 5.0.0 for macOS arm64 reports `AVFoundation: YES`. [observed, `cv2.getBuildInformation()` in a throwaway environment] All statements below are read from the source, not run against the camera.

- Opens with `sessionPreset = AVCaptureSessionPresetMedium`. [doc: [L433](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L433)] The resulting frame size for this camera is unverified.
- Requests `kCVPixelFormatType_32BGRA` from the output, then converts BGRA to BGR with `cvtColor` and copies again in `retrieveFrame`. [doc: [L412](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L412), [L640-L642](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L640-L642), [L296](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L296)] So the native `420v` frame is converted by the system to BGRA, then converted and copied twice more. Cost per 1920x1080 frame is unverified.
- `CAP_PROP_FRAME_WIDTH`/`HEIGHT` write `kCVPixelBufferWidthKey`/`HeightKey` into the output's `videoSettings` and then adopt whatever `activeFormat` reports; `activeFormat` itself is never set. Both properties must be set before the change applies. [doc: [L446-L471](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L446-L471), [L511-L530](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L511-L530)] Whether a request for 1920x1080, 1552x1552 or 1328x1760 yields that native format or a rescale of another is unverified.
- Readable properties: frame width, frame height, FPS, format. Settable: width, height, FPS. Everything else returns unknown or false, including `CAP_PROP_POS_MSEC`, exposure, white balance, buffer size. [doc: [L474-L555](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L474-L555)]
- `CAP_PROP_FPS` sets both frame durations to the minimum frame duration of the range whose maximum rate is nearest the request. With one 15 to 30 fps range per format the only reachable value is 30 fps, pinned. [doc: [L531-L548](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L531-L548)]
- Frame handoff is a one-slot mailbox: the delegate replaces the held buffer on every callback, with `alwaysDiscardsLateVideoFrames = YES`. `grab()` waits up to 1 s for the next signal. A slow consumer silently skips frames; no drop count and no timestamp. [doc: [L589-L607](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L589-L607), [L609-L623](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L609-L623), [L275-L290](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L275-L290), [L429](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L429)]
- Device index is the position after sorting video and muxed devices by `uniqueID`. [doc: [L362-L386](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L362-L386)] On this machine that list was [MacBook Pro Camera, iPhone Continuity Camera] before and after sorting, so index 0 was the built-in camera; the Desk View devices did not appear in it. [observed] A different Continuity Camera or external camera can reorder it.
- If authorization is not yet granted, the open requests access and fails in the same call ("not authorized to capture video ... requesting", then "camera failed to properly initialize"). The first run fails; rerun after granting. `OPENCV_AVFOUNDATION_SKIP_AUTH=1` disables the request. [doc: [L318-L358](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L318-L358), [L263-L265](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L263-L265)]
- No Center Stage handling anywhere in the file. [doc: same file] Center Stage control is a class-level property, so a PyObjC call in the same process before opening may still apply; unverified.

### PyObjC with AVFoundation

- Packages: `pyobjc-framework-AVFoundation` 13.0 (Python 3.11+, universal2 wheels through CPython 3.14), which depends on the CoreMedia and Quartz bindings; `pyobjc-framework-libdispatch` for the delegate queue. [doc: [PyPI](https://pypi.org/project/pyobjc-framework-AVFoundation/), [libdispatch notes](https://pyobjc.readthedocs.io/en/latest/apinotes/libdispatch.html)]
- Present in the bindings: `AVCaptureSession`, `AVCaptureDeviceInput`, `AVCaptureVideoDataOutput`, `AVCaptureDeviceDiscoverySession`, the `AVCaptureVideoDataOutputSampleBufferDelegate` protocol, `CMSampleBufferGetPresentationTimeStamp`, `CMSampleBufferGetImageBuffer`, `CMClockGetHostTimeClock`, `CMSyncConvertTime`, `CVPixelBufferLockBaseAddress`, `CVPixelBufferGetBaseAddressOfPlane`, `dispatch_queue_create`. The 7 formats and the Center Stage class properties read back correctly from Python. [observed, Python 3.13.13, PyObjC 13.0, throwaway environment]
- The API notes list no restriction on the capture classes or on `CMSampleBuffer` timing calls. [doc: [AVFoundation notes](https://pyobjc.readthedocs.io/en/latest/apinotes/AVFoundation.html), [CoreMedia notes](https://pyobjc.readthedocs.io/en/latest/apinotes/CoreMedia.html)]
- Everything in the sections above is reachable: native format and frame rate selection, `420v` delivery by setting `videoSettings` to an empty dictionary ("device-native format"), timestamps, drop callbacks, Center Stage control. [doc: [videoSettings](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutput/videosettings)] An unconnected `AVCaptureVideoDataOutput` listed pixel types `2vuy`, `yuvs`, `420v`, `420f`, 32ARGB, `BGRA`. [observed]
- Costs and pitfalls:
  - The delegate runs Python on a dispatch queue thread, once per frame. "Python code that raises exceptions in callbacks ... will cause a hard crash." [doc: [libdispatch notes](https://pyobjc.readthedocs.io/en/latest/apinotes/libdispatch.html)]
  - "It is called periodically, so it must be efficient to prevent capture performance problems, including dropped frames." [doc: [captureOutput(_:didOutput:from:)](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutputsamplebufferdelegate/captureoutput(_:didoutput:from:))]
  - Per-frame bridge overhead, GIL contention with the processing thread, and the cost and mechanics of turning a locked `CVPixelBuffer` plane into a NumPy array are unverified. No capture was run.
  - Setter calls (`setCenterStageControlMode_`, `setCenterStageEnabled_`, `setActiveFormat_`) were not exercised. Unverified from Python.

### FFmpeg `avfoundation` input device

- Options: device by name or index, `-pixel_format`, `-framerate` (default `ntsc`, 30000/1001), `-video_size`. [doc: [ffmpeg-devices, avfoundation](https://ffmpeg.org/ffmpeg-devices.html#avfoundation)] The local build (ffmpeg 9.0.1) also lists `-drop_late_frames`, default true. [observed, `ffmpeg -h demuxer=avfoundation`]
- It sets the device's `activeFormat`, keeps a single current frame, and stamps packets from the sample buffer's presentation time. [doc: [`libavdevice/avfoundation.m` at n9.0.1, L399](https://github.com/FFmpeg/FFmpeg/blob/n9.0.1/libavdevice/avfoundation.m#L399), [L232-L236](https://github.com/FFmpeg/FFmpeg/blob/n9.0.1/libavdevice/avfoundation.m#L232-L236), [L1152-L1154](https://github.com/FFmpeg/FFmpeg/blob/n9.0.1/libavdevice/avfoundation.m#L1152-L1154)]
- No Center Stage or effect handling was found in that file; unverified beyond a keyword search.
- Reachable from Python through PyAV or a subprocess pipe; both unverified here. OpenCV 5.0.0's FFmpeg backend also maps a camera index to this device when built with libavdevice, and the wheel reports `avdevice: YES`. [doc: [`cap_ffmpeg_impl.hpp` L1213-L1237](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_ffmpeg_impl.hpp#L1213-L1237); observed build info] How a frame rate that the device rejects (30000/1001 against a 15 to 30 range) is handled is unverified.

Not investigated: GStreamer `avfvideosrc`, CoreMediaIO property access, a native Swift helper feeding Python over shared memory.

## Camera permission for a terminal-launched Python process

- macOS 10.14+ requires user authorization for capture. Status is read with `AVCaptureDevice.authorizationStatus(for: .video)`; the system prompts on the first `AVCaptureDeviceInput` creation or on `requestAccess(for:)`. Until granted "the system only vends black video frames". [doc: [requestAccess(for:completionHandler:)](https://developer.apple.com/documentation/avfoundation/avcapturedevice/requestaccess(for:completionhandler:))]
- The grant belongs to the responsible code, not to the Python binary: for a tool "run by the user from Terminal", "the tool's responsible code is Terminal". "The exact algorithm it uses for this is not documented, has changed in the past, and may well change in the future." [doc: [Apple DTS, Developer Forums thread 756510](https://developer.apple.com/forums/thread/756510)] So the prompt names the terminal app (Terminal, iTerm2, an IDE's integrated terminal), and each launcher holds its own grant.
- Grants are listed and toggled in System Settings > Privacy & Security > Camera. [doc: [Control access to the camera on Mac](https://support.apple.com/guide/mac-help/control-access-to-your-camera-mchlf6d108da/mac)]
- `NSCameraUsageDescription` is required of apps that use the camera, and starting a session without it "raises an exception". [doc: [NSCameraUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nscamerausagedescription), [requestAccess](https://developer.apple.com/documentation/avfoundation/avcapturedevice/requestaccess(for:completionhandler:))] A bare `python` has no Info.plist of its own; that the terminal's usage description satisfies this is unverified and depends on the terminal app.
- Reset with `tccutil reset Camera`, as OpenCV's own error text advises. [doc: [cap_avfoundation_mac.mm L324](https://github.com/opencv/opencv/blob/5.0.0/modules/videoio/src/cap_avfoundation_mac.mm#L324)]
- `authorizationStatus(for: .video)` returned 3 (authorized) from the session that ran this research. [observed] That reflects that session's launcher only; the terminal used for the prototype may still be undetermined.

## Must be measured on the machine

1. **Field of view per format.** Horizontal and vertical field of view of each of the 7 formats against a target of known size and distance; whether formats are crops or rescales of each other; from that, pixels per millimetre at the eye at working distance. Decides which format to record.
2. **Reframing.** Whether Center Stage, the Video menu zoom (0.5x/1x) and pan change the frames a Python process receives; whether `.app` control mode with enabled false holds for a whole session; `isCenterStageActive` logged per run.
3. **Intrinsics and distortion.** Checkerboard calibration per chosen format; stability across sessions and reboots; whether the system already corrects distortion.
4. **Latency.** Callback time minus presentation timestamp on the host clock; light-to-timestamp delay with an LED or screen flash; per route and per format. Confirm the synchronization clock is the host time clock.
5. **Frame rate and jitter.** Delivered rate and inter-frame interval distribution at default settings and with both frame durations pinned to 1/30 s, in bright and dim light.
6. **Exposure and white balance.** Whether any mode becomes supported in a running session; brightness and colour drift over a session; motion blur at the iris in dim light.
7. **ISP processing.** Whether denoising or temporal filtering smears sub-pixel iris displacement; effect state (Portrait, Studio Light, Background, Reactions) as seen by the actual capture process.
8. **OpenCV behaviour.** Frame size from the default open; the size actually delivered for each requested size and whether it is native or rescaled; conversion and copy time per frame; device index with and without a phone nearby.
9. **PyObjC behaviour.** Per-frame callback overhead, buffer-to-NumPy cost for the luma plane, GIL contention, drop count from `didDrop` under load; the untested setter calls.
10. **Permission flow.** Which app is named in the prompt for the terminal in use, and whether a bare `python` starts a session without a usage-description exception.

## Appendix: how the observed values were read

Read-only queries; nothing below opens the camera or prompts.

- `system_profiler SPCameraDataType`, `sysctl -n hw.model`, `sw_vers`.
- A Swift script (Command Line Tools, macOS 15.5 SDK) and the same queries from PyObjC 13.0, using `AVCaptureDevice.DiscoverySession` over `.builtInWideAngleCamera`, `.deskViewCamera`, `.continuityCamera`, `.external`, then per device `formats`, `activeFormat`, `activeVideoMinFrameDuration`, `activeVideoMaxFrameDuration`, `isExposureModeSupported`, `isWhiteBalanceModeSupported`, `isFocusModeSupported`, `isCenterStageActive`, and per format `videoSupportedFrameRateRanges`, `isCenterStageSupported`, `videoFrameRateRangeForCenterStage`, `isPortraitEffectSupported`, `isStudioLightSupported`, `reactionEffectsSupported`, `isAutoVideoFrameRateSupported`. Class properties: `authorizationStatus(for:)`, `centerStageControlMode`, `isCenterStageEnabled`, `isPortraitEffectEnabled`, `isStudioLightEnabled`, `reactionEffectsEnabled`, `reactionEffectGesturesEnabled`, `isBackgroundReplacementEnabled`.
- API availability: `grep` of `AVCaptureDevice.h` and `AVCaptureSession.h` in the macOS 15.5 SDK for `API_UNAVAILABLE(macos` on the properties named above.
- `cv2.getBuildInformation()` from `opencv-python-headless` 5.0.0 and the PyObjC probes ran in throwaway `uv run --with` environments (Python 3.13.13), not the system Python.
- Clock check: `CMTimeGetSeconds(CMClockGetTime(CMClockGetHostTimeClock()))` bracketed by two `time.monotonic()` reads, 3 times.

Minimal reproduction of the format table:

```swift
import AVFoundation
let s = AVCaptureDevice.DiscoverySession(deviceTypes: [.builtInWideAngleCamera], mediaType: .video, position: .unspecified)
for d in s.devices {
    for f in d.formats {
        let dim = CMVideoFormatDescriptionGetDimensions(f.formatDescription)
        print(dim.width, dim.height, f.videoSupportedFrameRateRanges.map { ($0.minFrameRate, $0.maxFrameRate) })
    }
}
```
