# Replayable baselines: existing trackers and pretrained gaze estimators

Ticket: #16. Checked 2026-11-14. Target: MacBook Pro M4 Pro, macOS, Python, recorded 1920x1080 frames, nothing leaves the machine.

Nothing was installed or run. "read" means source code or a licence file was read. "derived" means computed here from cited numbers. "unverified" means not traced to a primary source or not tested. Method background is in [method-families][MF] and is not repeated.

## Answer

Replayable here, ranked by value as a baseline times effort to replay:

1. **ptgaze** with its ETH-XGaze, MPIIFaceGaze and MPIIGaze models. MIT code and weights, pure-Python wheel, takes `--video`, weights on Hugging Face ([PTG], [PTG-HF]). Calibration-free.
2. **UniGaze**. Best published cross-dataset accuracy found, pip package, weights on Hugging Face, non-commercial licence ([UG], [UG-HF], [UG-lic]). Calibration-free.
3. **FAZE**. The only pretrained estimator with built-in few-shot personal calibration, and the best model in the only offline replay of laptop webcam video found: 2.44° ([SX23]). Official weights still served ([FZ]). Linux, CUDA, live-camera demo: most porting work.
4. **L2CS-Net**. MIT, no camera intrinsics needed, stateless per frame. Official weights link is dead; the one mirror found holds only the Gaze360 model ([L2-47], [L2-PF]).
5. **EyeTrax**. MIT, MediaPipe landmarks plus ridge regression trained from calibration samples by API, outputs screen points ([ET]). No published accuracy. Uses wall-clock timestamps.
6. **WebGazer**. GPLv3, browser only, but its authors ship a tool that replays recorded webcam video through it in Chrome, with calibration fed by API ([WG-x]). Current version has no published accuracy of its own.

Ruled out or parked: iTracker (phone and tablet output space), `GazeTracking` (antoinelame; ratios, not gaze), PyGaze (hardware-tracker wrapper), OpenGaze (C++/Caffe, Ubuntu), GazeRecorder/GazeCloudAPI (vendor-hosted script), Beam (live camera only, SDK terms), 3DGazeNet (no licence), OpenFace 2.2 and 3.0 (licence and build effort; kept as optional geometric reference). Reasons below.

- No candidate publishes ≤ 1.5° under conditions like the target. Nearest: FAZE 2.44°, ETH-XGaze 3.40°, MPIIGaze 3.70° on home-laptop video at about 50 cm with 16-point calibration, 65 participants, winsorized means ([SX23]).
- Calibration-free estimators (ranks 1, 2, 4) output a 3D gaze direction in camera coordinates, not a point of gaze. Comparing them needs a per-user mapping to the screen fitted on the calibration pool, the same for all of them.
- Estimators that normalise the face (ranks 1 to 3) need camera intrinsics. Without them each tool assumes its own: ptgaze sets focal length = image width ([PTG-cam], read), UniGaze's video script 4 × image width ([UG-vid], read). That is about 53° and 14° horizontal field of view (derived). Intrinsics of this camera are not available from macOS and must be measured ([CAM]).
- Every strong pretrained model is non-commercial: CC BY-NC-SA 4.0, ModelGo NC, NVIDIA non-commercial, CMU academic, or MIT weights trained on non-commercial datasets. All allow private evaluation; none can ship in a product.

## Comparison

Accuracy is mean angular error unless stated. "PI" = person-independent. "LOPO" = leave-one-person-out. "XD" = cross-dataset. cm figures are not converted: no source gives viewing distance for them.

| Candidate | Licence | Input it expects | Per-user calibration | Published accuracy (dataset, protocol) | Runs here from Python on recorded frames |
|---|---|---|---|---|---|
| ptgaze 0.3.0 | Code and weights MIT; training data CC BY-NC-SA 4.0 (MPII) or ETH research agreement ([PTG-HF]) | BGR frame or video file; MediaPipe landmarks and head pose, normalised 224x224 face (ETH-XGaze, MPIIFaceGaze) or 36x60 grey eye (MPIIGaze); camera matrix from file, else dummy ([PTG], [PTG-cam]) | None. Outputs gaze pitch/yaw, 3D vector | ETH-XGaze ResNet-18: 4.878°, held-out 10-subject validation split, single run. MPIIFaceGaze: 4.83° LOPO. MPIIGaze: 5.73° LOPO. All by the weights' author ([PTG-HF]) | Yes. `py3-none-any` wheel, Python ≥ 3.10, torch ≥ 2.7, mediapipe ≥ 0.10.30 ([PTG-pypi]); `--video`, `--image` ([PTG]). CLI device `cpu` or `cuda` only ([PTG-main], read); MPS untested. "only been tested on Ubuntu" ([PTG]) |
| UniGaze 0.1.3 | ModelGo MG-NC-RAI-2.0: non-commercial use, reproduction and derivatives allowed ([UG-lic]) | Normalised face image; video script uses `face_alignment` 68 landmarks, head pose from a 6-point face model and a dummy camera, normalisation at focal 960, distance 600 ([UG-vid], read) | None | Released `unigaze_h14_cross_X` (trained ETH-XGaze): 5.57° on MPIIFaceGaze, 6.53° EYEDIAP, 6.56° GazeCapture, XD ([UG], Table 2a). Released `*_joint` (all five datasets): H-14 5.08° MPIIFaceGaze test subjects, 3.20° GazeCapture ([UG], Table 6) | Probably. `py3-none-any` wheel pinning `timm==0.3.2` ([UG-pypi]); weights as safetensors on HF ([UG-HF]); `predict_gaze_video.py -i` on video ([UG-repo]). Script picks `cuda` else `cpu` ([UG-vid], read). ViT-H CPU speed and timm 0.3.2 with current torch: unverified |
| FAZE | NVIDIA Source Code License: "non-commercially ... research or evaluation purposes only" ([FZ-lic]) | Normalised eye-region patches from HRNet landmarks and EOS face fit ([FZ-demo]); camera intrinsics; monitor pose from mirror calibration ([FZ-demo]) | Yes, k-shot fine-tuning; demo collects 9 points and fine-tunes 1,000 steps ([FZ-demo], [FZ-run], read) | 3.42° MPIIGaze and 3.18° GazeCapture at k = 3; 3.14° at k = 9 on MPIIGaze ([PA19]). 2.44° on home-laptop video, 16-point calibration, 65 participants ([SX23]) | Hard. Weights: training zip 1.25 GB and demo zip 25.6 MB, both HTTP 200 on 2026-11-14 ([FZ], [FZ-demo]). Tested on Ubuntu 16.04, PyTorch 1.3, CUDA 10.1; demo calls `v4l2-ctl` and opens a live `cv2.VideoCapture(0)` ([FZ-demo], [FZ-run], read). Recorded frames need a replaced frame source and calibration loop |
| L2CS-Net | MIT ([L2-repo]); weights trained on Gaze360 or MPIIGaze | BGR frame; RetinaFace crop resized to 224x224; no normalisation, no intrinsics ([L2-pipe], read) | None | 3.92° MPIIGaze LOPO; 10.41° Gaze360 front 180° ([L2], sec. 4). The mirrored Gaze360 model has only the 10.41° figure; no laptop-domain number | Yes once weights are found. `Pipeline.step(frame)` per frame ([L2-pipe]). Official Drive folder returns 404 (2026-11-14); open issue "Stale pre-trained model google drive link" ([L2-47]). Py-Feat mirror: Gaze360 ResNet-50 only, as safetensors, licence "mit-code-with-gaze360-research-terms" ([L2-PF]); conversion fidelity unverified. Detector branches `cpu` vs `gpu_id` ([L2-pipe], read), so MPS is unverified |
| EyeTrax | MIT ([ET]) | BGR frame; MediaPipe Face Landmarker, eye landmarks rotated to a face frame plus yaw/pitch/roll ([ET-src], read) | Yes. `train(X, y)` on features and screen points; ridge default, also elastic net, SVR, tiny MLP ([ET-src], read) | None published | Yes. `extract_features(frame)` per frame. Timestamps for MediaPipe VIDEO mode come from `time.time()` ([ET-src], read), so its landmark filter follows replay speed, not the stream clock |
| WebGazer | GPLv3; LGPLv3 option for companies under $1M ([WG]) | Browser video element or canvas; TF FaceMesh tracker, ridge regression ([WG-x], read) | Yes, continuous from clicks and cursor moves; `recordScreenPosition(x, y, type)` feeds samples ([WG], [WG-x], read) | Current version: none of its own; README says publications no longer correspond ([WG]). On Eye of the Typer video: 7.79 cm initial, 11.62 cm final dot test, L1 point-of-gaze error ([WE], sec. 5.3). 2016 version: 4.17°, chin rest ([PP16], via [MF]) | Not Python. Authors' `webgazerExtractServer.py` plus `webgazerExtractClient.html` replays dataset video frames in Chrome and writes per-frame CSV ([WG-data], [WG-x]). Local only |
| WebEyeTrack (BlazeGaze) | MIT ([WE-repo]) | BGR frame; MediaPipe landmarks, eye patch, intrinsics estimated from first frame ([WE-src], read) | Yes, MAML few-shot: `adapt_from_gaze_results(results, norm_pogs)` ([WE-py]) | 4.56 cm MPIIFaceGaze, 2.32 cm GazeCapture, k = 9 within-dataset ([WE], Table 1). 7.24 cm initial, 8.72 cm final on Eye of the Typer, XD ([WE], sec. 5.3) | Maybe. `process_frame(frame)` ([WE-py]); weights bundled ([WE-tree]). TensorFlow 2.11, tested on Ubuntu 24.04 ([WE-py]); macOS unverified. Calibration buffer pruned by `time.time()` ([WE-src], read) |
| OpenFace 2.2 | CMU academic or non-profit "or self", non-commercial internal research only; derivatives owned by CMU ([OF-lic]) | Video file `-f` or image directory `-fdir`; optional `-fx -fy -cx -cy` ([OF-cli]) | None. Geometric: ray through pupil intersected with eyeball sphere ([OF2], sec. III-C) | 9.10° MPIIGaze XD, 750-image subset ([OF2], Table V) | C++ only. Mac build by Homebrew, author has no Mac to test ([OF-mac]); Apple Silicon unverified |
| OpenFace 3.0 | CMU academic non-commercial, as above ([OF3-lic]) | Face crop from RetinaFace; STAR landmarks; multitask net outputs yaw/pitch ([OF3-repo]) | None | 2.56° MPIIGaze, 10.6° Gaze360 ([OF3], Table III); split not stated | Probably: Python, `pip install openface-test`, weights on HF; device `cpu` or `cuda` ([OF3-repo]) |
| GazeFollower | CC BY-NC-SA 4.0 ([GF]) | Frames from a `Camera` class (subclassable), MediaPipe, MNN model ([GF-more], [GF-req]) | Yes; pluggable `Calibration.calibrate(features, labels)` ([GF-more]) | Paper paywalled: unverified | Maybe. Pins `mediapipe==0.10.10` ([GF-req]); macOS arm64 wheel for that version unverified |
| GazeTR-Hybrid | CC BY-NC-SA 4.0 ([GT-repo]) | 224x224 face ([GT], sec. 4), normalised by GazeHub preprocessing ([GT-repo]) | None | Released weights: ETH-XGaze pre-trained only. Published 4.00° MPIIFaceGaze, 5.17° EyeDiap, after fine-tuning on each ([GT], Table 1). Not evaluated as released | Weights resolve on Drive (`GazeTR-H-ETH.pt`). No inference pipeline; `.cuda()` hard-coded ([GT-repo]) |
| ETH-XGaze official ResNet-50 | Code CC BY-NC-SA 4.0 ([XG-repo]) | Normalised 224x224 face; dlib landmarks in `demo.py` ([XG-repo]) | None in demo; paper fine-tunes on 200 samples ([XG], sec. 4.5) | 4.5° within-dataset; trained ETH-XGaze, tested MPIIGaze: 7.5° XD ([XG], Tables 2, 3) | Weights resolve on Drive (`epoch_24_ckpt.pth.tar`). Python 3.5, PyTorch 1.1 ([XG-repo]). Superseded here by ptgaze and UniGaze for this training set |
| MobileGaze (yakhyo) | MIT ([YK]) | Face crop; ONNX or PyTorch | None | 11.33 to 13.07° "MAE" on Gaze360, protocol not stated ([YK]) | Yes, ONNX weights in GitHub releases ([YK]). Low value: Gaze360-only training |

## Candidate notes

### ptgaze

- The demo and its weights are by a third party (hysts), not by the dataset authors. The ETH-XGaze model "is not one of the baseline models provided by the dataset authors" ([PTG-HF]).
- Face landmarks: MediaPipe in VIDEO mode, with synthetic monotonically increasing timestamps; the code comment claims "the frame interval value itself does not matter" ([PTG-fl], read). MediaPipe VIDEO mode applies a one-euro filter that uses time ([LM]), so that claim is unverified.
- MPIIGaze and MPIIFaceGaze labels use the original normalisation; their outputs "can contain a small systematic bias (on the order of a degree)" as 3D directions ([PTG]). A per-user mapping absorbs a constant bias.

### UniGaze

- Table 2a (trained on ETH-XGaze only) is the fairest published proxy for an unseen laptop user: 5.57° on MPIIFaceGaze against 6.75° for ResNet-50 and 7.09° for GazeTR-50 under the same protocol ([UG]).
- The joint models saw MPIIFaceGaze, GazeCapture and EYEDIAP training subjects ([UG], sec. 4.6); their test figures are within-domain, not cross-dataset.
- Licence forbids using outputs for fully automated decisions affecting legal rights and similar listed purposes ([UG-lic], 2.2(c)); none apply to private evaluation.

### FAZE

- [SX23] is the only found study that replays recorded laptop-webcam sessions through pretrained estimators offline: MPIIGaze, ETH-XGaze and FAZE "open-source implementations, with default image processing and data normalization steps", 29.9 fps recordings, sitting distance 50 cm. Accuracy 3.70°, 3.40°, 2.44°; RMS precision 2.33°, 1.80°, 0.47°. Inference 12, 4 and 1 fps on their hardware. Which implementations: unverified.
- The demo needs the monitor's pose relative to the camera from a mirror routine ([FZ-demo]). For a laptop the camera sits in the lid above the screen, so a fixed geometry could stand in; not checked.

### L2CS-Net

- The Py-Feat card states "Gaze360 test split: ~3.92° MAE" and "MPIIFaceGaze leave-one-out: ~4.16° MAE" ([L2-PF]); the paper reports 3.92° on MPIIGaze and 10.41° on Gaze360, and no 4.16° ([L2], abstract, sec. 4). Its other claims need checking.
- The MPIIGaze-trained models (the 3.92° ones) were not found mirrored.
- `.pkl` weights load with `torch.load`, which unpickles code; prefer the safetensors mirror or the official file if it returns.

### EyeTrax, WebEyeTrack, GazeFollower, EyeGestures

- These are complete per-user calibrated trackers in Python: frame in, screen point out. They are the closest in kind to the project, and none publishes accuracy except WebEyeTrack (cm, no distance).
- EyeGestures: GPLv3, `step(frame, calibrate, w, h)` on frames, Rust "V4" engine shared with the web version, built-in calibration ([EG]). No published accuracy. Python wheel on macOS arm64: unverified.

### WebGazer

- Replay path is the authors' own: the extract client draws each video frame to a canvas set with `setVideoElementCanvas`, seeks the screen recording by `currentTime`, and replays logged clicks and moves through `recordScreenPosition` ([WG-x], read). Calibration samples from the project's calibration pool could be fed the same way; untested.
- The extract client ships its own `webgazer.js` build next to it ([WG-tree]); which version: unverified.

### OpenFace

- The only geometric eye-model baseline found. [MF] ranks pure geometric methods weakest on webcam eyes; OpenFace 2.0's 9.10° XD fits that. Useful only to test the geometric hypothesis directly.
- OpenFace 3.0's 2.56° MPIIGaze beats every other number here, but no subject split was found in its experiment section ([OF3], sec. IV). Treat as unverified until the protocol is known.

## Ruled out or parked

- **iTracker (GazeCapture).** Research-only licence ([GC-lic]). Trained on iPhone and iPad; output is cm in a device-camera frame ([GC]). PyTorch checkpoint in the repo, 2.46 cm on GazeCapture, "Requires CUDA" ([GC-pt]). Wrong output space for a laptop.
- **`GazeTracking` (antoinelame).** MIT, but returns pupil coordinates and 0 to 1 horizontal and vertical ratios, no screen mapping ([GTk]); its "calibration" picks a binarisation threshold ([GTk-cal], read). Bundles the dlib 68-point model ([GTk-tree]), trained on 300-W, non-commercial ([LM]). No published accuracy. Not a gaze estimator.
- **PyGaze.** GPLv3 wrapper for hardware trackers (EyeLink, Tobii, SMI, EyeTribe, Alea, EyeLogic) ([PyG-tree]). Its "OpenGaze" backend talks to the GazePoint server on port 4242 ([PyG-og], read), not a webcam.
- **OpenGaze (Zhang et al.).** C++ with custom Caffe layers, Unix install guide and `.deb`, last commit 2020-06-04 ([OG]). Licence file not read: unverified.
- **GazeRecorder / GazeCloudAPI.** Browser script loaded from `api.gazerecorder.com` ([GR]). Where frames are processed is not stated: unverified, so it cannot be assumed local. Desktop GazeRecorder app: not checked.
- **Beam Eye Tracker.** Site lists Windows, Linux and macOS ([BM]). The SDK reads tracking from the running app; the FAQ prohibits collecting data to "reverse engineer or replicate the Beam Eye Tracker" ([BM-dev]). Feeding recorded frames would need a virtual camera: unverified.
- **Eyedid SDK (VisualCamp, formerly SeeSo).** Commercial; platform list and licence terms not stated on the docs home page ([EY]). Not checked further.
- **3DGazeNet (ECCV 2024).** Weights on Drive, demo on videos ([3DG]), but no licence file, so no rights granted (unverified reading of GitHub default terms).

## Before baselines can be run

1. **Camera intrinsics for the recorded format.** Normalising estimators otherwise disagree on geometry (focal = width vs. 4 × width, above). Checkerboard calibration is already listed as a measurement in [CAM].
2. **One gaze-direction-to-screen mapping for all calibration-free baselines.** Options: fit an affine or low-order map from yaw/pitch to screen point on the calibration pool, or intersect the 3D ray with the screen plane using measured screen pose plus a personal offset. The choice changes the scores; fix it before comparing.
3. **A replay harness that owns the clock.** ptgaze, EyeTrax and WebEyeTrack set MediaPipe or calibration timestamps themselves (synthetic or wall clock, above). The harness should feed frames in order with stream timestamps where the API allows, and log where it does not.
4. **Throughput is offline only for some.** ViT-H (UniGaze) and FAZE on CPU are likely below camera rate (1 to 4 fps on unspecified hardware in [SX23]); fine for replay, not for live comparison.

## Not verified

- Nothing was installed or run: macOS arm64 install, MPS support and per-frame time for every candidate.
- Whether ptgaze's synthetic MediaPipe timestamps change its output relative to real ones.
- UniGaze with `timm==0.3.2` on a current macOS torch.
- L2CS mirror weights match the original release; whether MPIIGaze-trained L2CS weights exist anywhere else.
- ETH-XGaze dataset agreement terms on model use (only the ptgaze model card's summary was read, [PTG-HF]).
- [SX23]: which implementations and weights, and the calibration regression (deferred there to Saxena et al. 2022, not read).
- OpenFace 3.0 MPIIGaze split; GazeFollower published accuracy (paper paywalled); WebGazer version in [WE]'s comparison.
- Where GazeCloudAPI processes frames; Beam with recorded frames; Eyedid platforms.
- 3DGazeNet licence status beyond the absent licence file.
- FAZE monitor geometry substitute for a built-in laptop camera.

## Sources

- [MF] Repo research, method families (#3). branch `research/method-families`, `docs/research/method-families.md`
- [LM] Repo research, landmark models (#4). branch `research/landmark-models`, `docs/research/landmark-models.md`
- [CAM] Repo research, camera. branch `research/camera`, `docs/research/camera.md`
- [SX23] Saxena, Fink, Lange. Deep learning models for webcam eye tracking in online experiments. Behavior Research Methods, 2023. https://doi.org/10.3758/s13428-023-02190-6 (read via PMC11133145)
- [PA19] Park et al. Few-Shot Adaptive Gaze Estimation. ICCV 2019. https://arxiv.org/abs/1905.01941
- [XG] Zhang et al. ETH-XGaze. ECCV 2020. https://arxiv.org/abs/2007.15837
- [UG] Qin, Zhang, Sugano. UniGaze. WACV 2026. https://arxiv.org/abs/2502.02307
- [L2] Abdelrahman et al. L2CS-Net. 2022. https://arxiv.org/abs/2203.03339
- [GT] Cheng, Lu. Gaze Estimation using Transformer. ICPR 2022. https://arxiv.org/abs/2105.14424
- [WE] Davalos et al. WebEyeTrack. 2025. https://arxiv.org/abs/2508.19544
- [OF2] Baltrušaitis et al. OpenFace 2.0. FG 2018. http://multicomp.cs.cmu.edu/wp-content/uploads/2018/11/OpenFace.pdf
- [OF3] Hu, Mathur, Liang, Morency. OpenFace 3.0. 2025. https://arxiv.org/abs/2506.02891
- [PP16] Papoutsaki et al. WebGazer. IJCAI 2016. https://www.ijcai.org/Proceedings/16/Papers/540.pdf

[MF]: https://github.com/bruno-rda/eye-tracker/blob/research/method-families/docs/research/method-families.md
[LM]: https://github.com/bruno-rda/eye-tracker/blob/research/landmark-models/docs/research/landmark-models.md
[CAM]: https://github.com/bruno-rda/eye-tracker/blob/research/camera/docs/research/camera.md
[SX23]: https://pmc.ncbi.nlm.nih.gov/articles/PMC11133145/
[PA19]: https://arxiv.org/abs/1905.01941
[XG]: https://arxiv.org/abs/2007.15837
[UG]: https://arxiv.org/abs/2502.02307
[L2]: https://arxiv.org/abs/2203.03339
[GT]: https://arxiv.org/abs/2105.14424
[WE]: https://arxiv.org/abs/2508.19544
[OF2]: http://multicomp.cs.cmu.edu/wp-content/uploads/2018/11/OpenFace.pdf
[OF3]: https://arxiv.org/abs/2506.02891
[PP16]: https://www.ijcai.org/Proceedings/16/Papers/540.pdf
[PTG]: https://github.com/hysts/pytorch_mpiigaze_demo
[PTG-HF]: https://huggingface.co/hysts/ptgaze-eth-xgaze-resnet18
[PTG-pypi]: https://pypi.org/project/ptgaze/0.3.0/
[PTG-main]: https://github.com/hysts/pytorch_mpiigaze_demo/blob/main/ptgaze/main.py
[PTG-cam]: https://github.com/hysts/pytorch_mpiigaze_demo/blob/main/ptgaze/common/camera.py
[PTG-fl]: https://github.com/hysts/pytorch_mpiigaze_demo/blob/main/ptgaze/head_pose_estimation/face_landmark_estimator.py
[UG-repo]: https://github.com/ut-vision/UniGaze
[UG-vid]: https://github.com/ut-vision/UniGaze/blob/main/unigaze/predict_gaze_video.py
[UG-HF]: https://huggingface.co/UniGaze/UniGaze-models
[UG-pypi]: https://pypi.org/project/unigaze/0.1.3/
[UG-lic]: https://github.com/ut-vision/UniGaze/blob/main/LICENSE.txt
[FZ]: https://github.com/NVlabs/few_shot_gaze
[FZ-lic]: https://github.com/NVlabs/few_shot_gaze/blob/master/LICENSE
[FZ-demo]: https://github.com/NVlabs/few_shot_gaze/blob/master/demo/README.md
[FZ-run]: https://github.com/NVlabs/few_shot_gaze/blob/master/demo/run_demo.py
[L2-repo]: https://github.com/Ahmednull/L2CS-Net
[L2-pipe]: https://github.com/Ahmednull/L2CS-Net/blob/main/l2cs/pipeline.py
[L2-47]: https://github.com/Ahmednull/L2CS-Net/issues/47
[L2-PF]: https://huggingface.co/py-feat/l2cs
[ET]: https://github.com/ck-zhang/EyeTrax
[ET-src]: https://github.com/ck-zhang/EyeTrax/blob/master/src/eyetrax/gaze.py
[WG]: https://github.com/brownhci/WebGazer
[WG-x]: https://github.com/brownhci/WebGazer/blob/master/www/data/src/webgazerExtractClient.js
[WG-tree]: https://github.com/brownhci/WebGazer/tree/master/www/data/src
[WG-data]: https://webgazer.cs.brown.edu/data/
[WE-repo]: https://github.com/RedForestAI/WebEyeTrack
[WE-py]: https://github.com/RedForestAI/WebEyeTrack/blob/main/python/README.md
[WE-src]: https://github.com/RedForestAI/WebEyeTrack/blob/main/python/webeyetrack/webeyetrack.py
[WE-tree]: https://github.com/RedForestAI/WebEyeTrack/tree/main/python/webeyetrack/model_weights
[OF-lic]: https://github.com/TadasBaltrusaitis/OpenFace/blob/master/OpenFace-license.txt
[OF-cli]: https://github.com/TadasBaltrusaitis/OpenFace/wiki/Command-line-arguments
[OF-mac]: https://github.com/TadasBaltrusaitis/OpenFace/wiki/Mac-installation
[OF3-repo]: https://github.com/CMU-MultiComp-Lab/OpenFace-3.0
[OF3-lic]: https://github.com/CMU-MultiComp-Lab/OpenFace-3.0/blob/main/LICENSE
[GF]: https://github.com/GanchengZhu/GazeFollower
[GF-more]: https://github.com/GanchengZhu/GazeFollower/blob/main/MORE_INFO.md
[GF-req]: https://github.com/GanchengZhu/GazeFollower/blob/main/requirements.txt
[GT-repo]: https://github.com/yihuacheng/GazeTR
[XG-repo]: https://github.com/xucong-zhang/ETH-XGaze
[YK]: https://github.com/yakhyo/gaze-estimation
[EG]: https://github.com/NativeSensors/EyeGestures
[GC]: https://github.com/CSAILVision/GazeCapture
[GC-lic]: https://github.com/CSAILVision/GazeCapture/blob/master/LICENSE.md
[GC-pt]: https://github.com/CSAILVision/GazeCapture/blob/master/pytorch/README.md
[GTk]: https://github.com/antoinelame/GazeTracking
[GTk-cal]: https://github.com/antoinelame/GazeTracking/blob/master/gaze_tracking/calibration.py
[GTk-tree]: https://github.com/antoinelame/GazeTracking/tree/master/gaze_tracking/trained_models
[PyG-tree]: https://github.com/esdalmaijer/PyGaze/tree/master/pygaze/_eyetracker
[PyG-og]: https://github.com/esdalmaijer/PyGaze/blob/master/pygaze/_eyetracker/opengaze.py
[OG]: https://git.cai.simtech.uni-stuttgart.de/public-projects/opengaze
[GR]: https://gazerecorder.com/gazecloudapi/
[BM]: https://beam.eyeware.tech/
[BM-dev]: https://beam.eyeware.tech/developers/
[EY]: https://docs.eyedid.ai/
[3DG]: https://github.com/eververas/3DGazeNet
