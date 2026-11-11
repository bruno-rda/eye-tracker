# Face and iris landmark models: candidates

Ticket: #4. Checked 2026-11-10. Target: MacBook Pro Mac16,8 (M4 Pro), macOS 15, Python.

## Answer

- Only two maintained, permissively usable candidates give eye-centre landmarks from Python on macOS: **MediaPipe Face Landmarker** (iris centre + 4 iris contour points per eye, 3D mesh, transformation matrix) and **Apple Vision** (one pupil point per eye, 2D, roll/yaw/pitch).
- No candidate has a published evaluation showing sub-pixel iris precision. The only iris-specific figure is MediaPipe Iris: 5.76 to 7.10 % of iris diameter mean absolute error, against a human annotation discrepancy of 4.01 % ([Iris card][iriscard], p. 5).
- No source documents inference time on Apple silicon for any candidate.
- Measure first: MediaPipe Face Landmarker, then Apple Vision, then (only if needed) the legacy MediaPipe iris model on a native-resolution eye crop.

## Outputs

| Candidate | Face landmarks | Iris / pupil | 2D / 3D | Head pose |
|---|---|---|---|---|
| MediaPipe Face Landmarker (FaceLandmarker-V2) | 478 ([docs][fl]) | 10 iris landmarks ([V2 card][v2card], p. 7); indices 469-472 and 474-477 are the contours ([source][flpy-src]) | x, y normalised to image; z relative, "scaled like x relative to the center of the head" ([Python guide][flpy]) | 4x4 matrix, canonical face to detected face, optional ([docs][fl], [source][flpy-src]); also 52 blendshapes |
| Apple Vision `VNDetectFaceLandmarksRequest` | 65 or 76 points; 76 needs revision 3, macOS 10.15+ ([SDK header][vn-const], [rev 3][vn-rev3]) | `leftPupil`, `rightPupil`: "the region containing the point where the left pupil is located", "may be inaccurate if the eye is blinking" ([docs][vn-pupil]). No iris contour ([region list][vn-lm2d]) | 2D, normalised to the face bounding box ([docs][vn-lm2d]) | `roll`, `yaw` (macOS 10.14+), `pitch` (macOS 12+), radians, nil "if the request doesn't calculate the angle" ([roll][vn-roll], [yaw][vn-yaw], [pitch][vn-pitch]). No matrix |
| MediaPipe Iris (legacy, standalone `iris_landmark.tflite`) | 71 eye and eyebrow landmarks per eye | 5 per eye: 1 pupil centre + 4 iris contour | 2D, pixel coordinates of a 64x64 eye crop ([Iris card][iriscard], p. 1) | none |
| ELG (GazeML) | none (single-eye input) | 18 per eye: "8 in the limbus region, 8 on the iris edge, 1 at the iris center, and 1 at the eyeball center" | 2D, from 75x45 heatmaps on a 150x90 eye image, soft-argmax "to find sub-pixel landmark coordinates" ([paper][elg], sec. 4) | none |
| OpenFace 2.2 | 68, 2D px and 3D mm | 56 eye-region landmarks, 2D px and 3D mm | both | translation mm, rotation rad ([output format][of-out]) |

## Reported error, speed, access

| Candidate | Authors' landmark error (data) | Authors' speed | Python | Maintenance | Licence |
|---|---|---|---|---|---|
| MediaPipe Face Landmarker | All 478 landmarks, 2D mean absolute error normalised by interocular distance: 2.62 % (SD 1.03) tracking mode, 3.24 % (SD 1.29) on the first frame; 1,700 smartphone front-camera selfies, 100 per each of 17 regions; human annotator discrepancy 2.56 % ([V2 card][v2card], pp. 5-6). No iris-only figure. Predecessor (Attention Mesh): eyes 6.04 %, normalised by eye-corner distance ([paper][attmesh], Table 2) | Attention Mesh: 16.6 ms, Pixel 2XL, TFLite GPU ([paper][attmesh], Table 1). None for V2; the task page lists no benchmark ([docs][fl]) | `pip install mediapipe`; `mp.tasks.vision.FaceLandmarker`; `detect`, `detect_for_video`, `detect_async` ([Python guide][flpy]). Wheel `mediapipe-1.2.2-py3-none-macosx_11_0_arm64.whl`, classifiers Python 3.9 to 3.14 ([PyPI][mp-pypi]). Model file downloaded separately ([docs][fl]) | v1.2.2 on 2026-11-03, five GitHub releases from v1.0.0 (2026-07-28) to v1.2.2 ([releases][mp-rel]). `face_landmarker.task` last modified 2023-05-03 (HTTP header of the [model URL][fl-task]); model card dated 2022-09-15 ([V2 card][v2card]) | Apache 2.0, code and model ([PyPI][mp-pypi], [V2 card][v2card]) |
| Apple Vision | None published. WWDC19: "the image on the right-hand side has pupils detected with much better accuracy" for revision 3, no number ([session 222][wwdc19]) | None published. "free to leverage the GPU" by default ([`usesCPUOnly`][vn-cpu]) | PyObjC: `pyobjc-framework-Vision` 13.0, 2026-10-30, Python >= 3.11, universal2 wheels ([PyPI][pyobjc]). The Swift `DetectFaceLandmarksRequest` (macOS 15+) is a separate API ([docs][vn-swift]) | System framework, macOS 10.13+ ([docs][vn-req]) | Proprietary system framework; terms not checked (unverified). PyObjC is MIT ([PyPI][pyobjc]) |
| MediaPipe Iris (legacy) | Iris: 5.76 to 7.10 % of iris diameter (white-to-white) mean absolute error across 17 regions, tracking mode; human discrepancy 4.01 % (139 samples, 8 annotators); 1,700 smartphone selfies ([Iris card][iriscard], p. 5). Paper: 7.16 % of inter-eye distance on about 4,000 images; manual annotation baseline 5.73 % frontal, 7.04 % hard ([paper][irispaper], sec. 5) | Eye refinement: 7 to 20 ms CPU, 2.6 to 12 ms GPU on five phones ([paper][irispaper], Table 1) | No Python API in the 1.2.2 wheel (see below). The `.tflite` is still hosted ([file][iris-tflite], last modified 2022-09-01) and could be run with LiteRT, which has macOS arm64 wheels ([PyPI][litert]); that path is unverified | Legacy; "upgraded to a new MediaPipe Solution" on 2023-05-10 ([iris.md][irismd]) | Apache 2.0 ([Iris card][iriscard]) |
| ELG (GazeML) | Iris localisation compared with ElSe and ExCuSe on BioID and GI4E; results only as curves ([paper][elg], Fig. 7) | "up to 26Hz on a desktop PC (Intel i7-4770 and Nvidia GeForce 1080Ti)" ([paper][elg], sec. 7) | TensorFlow scripts; "only been tested on an Ubuntu 16.04 system"; "re-implementations ... provided models should not be considered as reference" ([README][gazeml]) | Last push 2024-10, no releases ([repo][gazeml]) | MIT ([repo][gazeml]) |
| OpenFace 2.2 | Not looked up | "capable of real-time performance" from a webcam, no number ([README][openface]) | C++ executables; no Python API found (unverified) | Last release 2.2.0, 2019-07-13 ([repo][openface]) | "Academic or non-profit organization noncommercial research use only" ([licence][of-lic]) |

## MediaPipe Face Landmarker: details that affect measurement

- **Model input is a 256x256 face crop** with 25 % margin per side ([V2 card][v2card], p. 1). Camera resolution beyond that is discarded. The card lists a face that "can't be rescaled to model input ... without quality degradation" as out of scope (p. 2).
- **Built-in smoothing.** In VIDEO and LIVE_STREAM modes with `num_faces == 1`, landmarks pass a one-euro filter (min cutoff 0.05, beta 80, derivative cutoff 1.0) ([graph][fl-graph] l. 449-454, [detector graph][fl-det] l. 158-168). `FaceLandmarkerOptions` has no switch for it ([source][flpy-src]). IMAGE mode is unfiltered but has no tracking loop ([graph][fl-graph] l. 463), so the detector runs on every frame, the mode the card scores worse (3.24 % against 2.62 %).
- **Every frame processed:** `detect_for_video` is synchronous. `detect_async` "may drop the input images if needed" ([source][flpy-src]).
- **CPU only on macOS from Python:** "GPU support is currently limited to Ubuntu platforms" ([`base_options.py`][mp-base]).
- **Head pose:** the matrix maps the canonical face model, whose unit is a centimetre, to the detected face ([face_mesh.md][fmmd], "Canonical Face Model").
- **Legacy `mp.solutions` is gone from the wheel:** the 1.2.2 macOS wheel contains no file under `mediapipe/python/solutions/` and no `.tflite` or `.task` (wheel listing, 2026-11-10, [PyPI][mp-pypi]). Tutorials using `mp.solutions.face_mesh(refine_landmarks=True)` do not apply.
- **Intended use** is AR on smartphone selfie video ([V2 card][v2card], p. 2). The card warns of "increase of jittering" under poor light, noise or motion.

## Apple Vision: details

- Per-point `precisionEstimatesPerPoint` exists only with the 76-point constellation ([docs][vn-prec]).
- No 3D, no iris contour, no transformation matrix (tables above).
- ARKit face tracking (eye transforms) lists iOS and iPadOS only and needs a TrueDepth camera or Neural Engine device ([docs][arkit]); it is also a gaze estimator, so out of scope.
- Internal crop resolution, model and accuracy are undocumented.

## Is iris precision sub-pixel?

No published evaluation says so for any candidate.

- MediaPipe: the best published iris figure is error against human annotation, 5.76 to 7.10 % of iris diameter, and annotators themselves disagree by 4.01 % ([Iris card][iriscard], p. 5). That figure is for the 2020 iris model, not FaceLandmarker-V2, and is not frame-to-frame precision. Neither card reports precision.
- Apple Vision: nothing published.
- ELG: produces sub-pixel coordinates by construction (soft-argmax) but reports no sub-pixel precision measurement ([paper][elg]).
- Three web searches for third-party pixel-level precision studies of MediaPipe iris landmarks found none. That is a search result, not proof of absence.

Scale check (derived, unverified; uses the sibling ticket's assumed geometry of 1920 px across 70 degrees at 55 cm, iris about 29 px, 1 degree of eye rotation about 0.5 px):

- 5.76 to 7.10 % of 29 px is 1.7 to 2.1 px, about 3.3 to 4.1 degrees. The 4.01 % annotator floor is 1.2 px, about 2.3 degrees.
- A constant offset is removed by calibration; precision and gaze-dependent bias are what matter, and neither is published.
- Assuming a 15 cm face width (unverified), the face is about 374 px wide, the crop about 561 px, so the 256 px model input halves the scale: iris about 13 px, 1 degree about 0.23 px at the model input.
- The legacy iris model crops 2.3 times the eye-corner span ([ROI graph][iris-roi]) to 64 px. Assuming a 3 cm span (unverified) that is about 172 px to 64 px: iris about 11 px. It does not see more detail than V2.

## Not candidates

- **dlib 68-point predictor:** trained on iBUG 300-W, model "can't be used in a commercial product" per the dataset licence ([dlib-models][dlibm]); PyPI ships source only ([PyPI][dlib-pypi]). No iris landmarks (unverified beyond the 68-point scheme).
- **face-alignment (FAN):** 2D or 3D face landmarks, BSD-3, v1.5.0 on 2026-04-06, supports the `mps` device ([README][fan]). No iris landmarks mentioned.
- **InsightFace:** models are "for non-commercial research purposes only" ([README][insight]). Iris landmarks not mentioned (unverified).
- **OpenSeeFace:** 66 landmarks "close to iBUG 68", ONNX Runtime, 44 fps on one CPU core for the default model, BSD-2; the author states accuracy is hard to compare numerically and "tracking of the eye region can be less accurate" than MediaPipe; its eye model is a gaze and blink model trained on MPIIGaze ([README][osf]).
- **OpenFace 2.2:** non-commercial licence, unmaintained since 2019, and it bundles a gaze estimator (table above).

## Measure first

1. **MediaPipe Face Landmarker, VIDEO mode, CPU.** The only maintained candidate with iris contour and centre, 3D mesh and a head transform, Apache 2.0, one `pip install`. Measure inference time per frame on the M4 Pro and iris-centre precision during fixation, in camera pixels. Repeat in IMAGE mode to separate model spread from the one-euro filter.
2. **Apple Vision, 76 points, via PyObjC.** Independent second estimate of pupil position, native to the machine, free to use the GPU. Unknown accuracy and speed, so only measurement can rank it. Same two metrics.
3. **Legacy `iris_landmark.tflite` through LiteRT**, only if 1 is limited by its 256 px input. It has the only published iris-specific error, but the scale check above says it sees the iris no larger.

ELG is deferred: unmaintained re-implementation, TensorFlow on Ubuntu only. It is the one candidate whose input (150x90 per eye) would upsample the eye rather than shrink it, so it is the fallback if both leaders fail the precision target.

## Not verified

- Inference time of any candidate on Apple silicon (nothing published).
- Whether the MediaPipe GPU delegate works on macOS in 1.2.2 (docstring says no; not run).
- Number of points Vision returns in `leftPupil` at runtime, and whether the landmarks request populates roll, yaw and pitch.
- Apple's licence terms for Vision.
- Running `iris_landmark.tflite` under LiteRT on macOS.
- Absence of iris landmarks in dlib, FAN and InsightFace beyond what their READMEs list.
- OpenFace landmark error figures and Python access.
- The scale-check arithmetic: face width, eye-corner span and the sibling ticket's camera geometry are assumptions.

[fl]: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker
[flpy]: https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python
[v2card]: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf
[iriscard]: https://drive.google.com/file/d/1bsWbokp9AklH2ANjCfmjqEzzxO1CNbMu/view
[irispaper]: https://arxiv.org/abs/2006.11341
[attmesh]: https://arxiv.org/abs/2006.10962
[flpy-src]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/mediapipe/tasks/python/vision/face_landmarker.py
[fl-graph]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/mediapipe/tasks/cc/vision/face_landmarker/face_landmarker_graph.cc
[fl-det]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/mediapipe/tasks/cc/vision/face_landmarker/face_landmarks_detector_graph.cc
[mp-base]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/mediapipe/tasks/python/core/base_options.py
[fmmd]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/docs/solutions/face_mesh.md
[irismd]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/docs/solutions/iris.md
[iris-roi]: https://github.com/google-ai-edge/mediapipe/blob/v1.2.2/mediapipe/modules/iris_landmark/iris_landmark_landmarks_to_roi.pbtxt
[mp-rel]: https://github.com/google-ai-edge/mediapipe/releases
[mp-pypi]: https://pypi.org/project/mediapipe/1.2.2/#files
[fl-task]: https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
[iris-tflite]: https://storage.googleapis.com/mediapipe-assets/iris_landmark.tflite
[litert]: https://pypi.org/project/ai-edge-litert/#files
[vn-req]: https://developer.apple.com/documentation/vision/vndetectfacelandmarksrequest
[vn-const]: https://developer.apple.com/documentation/vision/vnrequestfacelandmarksconstellation
[vn-rev3]: https://developer.apple.com/documentation/vision/vndetectfacelandmarksrequestrevision3
[vn-lm2d]: https://developer.apple.com/documentation/vision/vnfacelandmarks2d
[vn-pupil]: https://developer.apple.com/documentation/vision/vnfacelandmarks2d/leftpupil
[vn-prec]: https://developer.apple.com/documentation/vision/vnfacelandmarkregion2d/precisionestimatesperpoint-5jl22
[vn-roll]: https://developer.apple.com/documentation/vision/vnfaceobservation/roll
[vn-yaw]: https://developer.apple.com/documentation/vision/vnfaceobservation/yaw
[vn-pitch]: https://developer.apple.com/documentation/vision/vnfaceobservation/pitch
[vn-cpu]: https://developer.apple.com/documentation/vision/vnrequest/usescpuonly
[vn-swift]: https://developer.apple.com/documentation/vision/detectfacelandmarksrequest
[wwdc19]: https://developer.apple.com/videos/play/wwdc2019/222/
[arkit]: https://developer.apple.com/documentation/arkit/arfacetrackingconfiguration
[pyobjc]: https://pypi.org/project/pyobjc-framework-Vision/
[elg]: https://arxiv.org/abs/1805.04771
[gazeml]: https://github.com/swook/GazeML
[openface]: https://github.com/TadasBaltrusaitis/OpenFace
[of-out]: https://github.com/TadasBaltrusaitis/OpenFace/wiki/Output-Format
[of-lic]: https://github.com/TadasBaltrusaitis/OpenFace/blob/master/OpenFace-license.txt
[dlibm]: https://github.com/davisking/dlib-models#shape_predictor_68_face_landmarksdatbz2
[dlib-pypi]: https://pypi.org/project/dlib/#files
[fan]: https://github.com/1adrianb/face-alignment
[insight]: https://github.com/deepinsight/insightface#license
[osf]: https://github.com/emilianavt/OpenSeeFace
