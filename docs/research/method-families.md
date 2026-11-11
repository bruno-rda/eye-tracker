# Webcam gaze estimation: method families and reported results

Ticket: #3. Scope: ordinary RGB camera, no infrared. Ideas and reported results only; no tracker is dissected.

Reading notes: "(abstract)" means only the abstract was read. "derived" means computed here from cited numbers. "unverified" means not traced to a source.

## Answer in brief

- The literature splits methods into 3D eye-model (geometric), 2D feature regression, and appearance-based; hybrids are a later, looser group ([HJ10], [CH24]).
- Without personal calibration every RGB family sits at about 4 to 7 degrees or worse; the person-specific offset between optical and visual axis alone is several degrees ([HJ10], [ZH19], [PK20]).
- A handful of calibration points buys most of the gain: about 4.5 to 6.4 degrees uncalibrated falls to about 2.7 to 3.2 degrees with 4 to 16 samples and 2.5 degrees with 60; returns flatten after about 9 ([ZH19], [CS20], [LI19], [PA19]).
- Head-to-head on a 1080p webcam, a calibrated appearance method reached 2.3 to 3.1 degrees while a calibrated landmark-fitted eye model reached 3.8 to 12.1 degrees ([ZH19]).
- About 1 to 1.4 degrees has been reported from webcams only with a head rest or virtual chin rest, long calibration or frequent recalibration ([XU15], [KA23]).
- No study found matches the target setup exactly (one user, built-in laptop camera, 50 to 60 cm, natural head movement, calibration of 30 s or less). The nearest evidence points to 2 to 3 degrees, about 1.9 to 2.9 cm on screen at 55 cm (derived).

## Taxonomy

- [HJ10] (survey, 2010): feature-based methods, split into 2D regression (interpolation) and 3D model-based; appearance-based methods; natural-light methods listed separately.
- [CH24] (survey and benchmark, 2024): 3D eye model recovery, 2D eye feature regression, appearance-based. It states the first two "usually" need dedicated devices such as infrared cameras, and that appearance-based methods work with off-the-shelf web cameras.
- Hybrids are not a class in either survey. [HJ10] anticipates them: combining geometry-based feature methods with appearance-based methods "could potentially benefit from the relative strengths of both".

## Comparison

Accuracy is mean angular error unless stated. "PI" = person-independent (no personal calibration). Low-resolution column answers: how does the family cope with an eye region where the iris is about 29 px wide and 1 degree of eye rotation moves the iris centre about 0.5 px (sibling-ticket figures, assumed 70 degree field of view at 55 cm, not re-derived here).

| Family | Idea | Input | Calibration | Reported accuracy and conditions | Low-resolution eye region | Fails when |
|---|---|---|---|---|---|---|
| Geometric (3D eye model) | Recover eyeball centre and iris or pupil centre in 3D; the line through them is the optical axis; rotate by a personal offset to the visual axis; intersect with the screen ([HJ10]). | Face and eye landmarks, head pose, camera intrinsics, screen pose relative to camera ([HJ10]). | Camera and screen geometry, plus personal parameters (axis offset, eyeball radius or position) from a few points ([HJ10], [WJ17]). | 3.5 degrees: 640x480 webcam, 45 to 65 cm, free head movement, 5-point calibration ([WJ17]). 6.88 degrees: tablet camera, 8 participants, calibration not stated ([WB14], abstract). 3.8 to 12.1 degrees with 60 calibration samples, 4.9 degrees at about 50 cm indoors: 1080p webcam, 20 participants ([ZH19]). 8.3 degrees PI cross-dataset on MPIIGaze+ ([PA18]). | Worst. Needs sub-pixel iris and eyeball-centre localisation; error grew with distance ([ZH19]); 17.3 degrees at about 13x6 px eyes ([WJ17]). | Small or noisy eye image, glasses, extreme gaze or head pose, unknown geometry ([ZH19], [WJ17], [HJ10]). |
| Feature regression | Extract a few 2D features (iris centre relative to eye corners, landmark positions, head pose) and fit a per-user map to screen coordinates ([HJ10], [SE12]). | Eye landmarks; optionally head pose ([PA18]). | Several on-screen points per session; no camera or screen geometry ([HJ10]). | 2 to 3 degrees, webcam, "standard working conditions" ([SE12], abstract). 4.6 degrees on MPIIGaze+ with 20 calibration samples, landmarks from a learned detector ([PA18]). 2 to 5 degrees with head pose combined, low-resolution video ([VA12], abstract). | Poor to moderate. Same landmark noise as geometric, but the fitted map absorbs systematic bias. | Head moves away from the calibration pose ([HJ10]); eye corners shift with gaze ([SE12]); few calibration points with a flexible map ([KR16]). |
| Appearance-based, classical | Regress screen point or gaze angle directly from eye-patch pixels with a per-user model ([HJ10]). | Eye image crops. | Many samples from the user, per session ([HJ10]). | 0.5 to 1.5 degrees, not head-pose invariant ([HJ10], table). Webcam, headrest, 56 cm: 1.06 degrees median on a 33-point test (one subject), 1.32 degrees mean against a reference tracker in free viewing (3 subjects) ([XU15]). | Good. [XU15] used eye patches downsampled to 6x10 px. | Head movement: appearance changes cannot be matched to calibration data ([XU15], [HJ10]); illumination change ([HJ10]). |
| Appearance-based, deep | A network trained on many people maps eye or face image (plus head pose) to gaze direction or screen point ([CH24]). | Eye or full-face crop; for direction output, camera intrinsics and screen pose to reach the screen ([ZH17]). | None required; a few points to personalise ([CH24]). | PI within-dataset on MPIIFaceGaze (laptop webcams): about 3.7 to 7.3 degrees across benchmarked methods ([CH24], table 5). PI cross-dataset: 10.8 degrees ([ZH17]). Person-specific, 2,500 training images: 2.5 degrees on MPIIGaze+ ([ZH17]). With 60 calibration samples: 2.3 to 3.1 degrees over 30 to 180 cm, 1080p webcam ([ZH19]). Phones: 1.71 cm uncalibrated, 1.34 cm with 13 points ([KR16]). | Best evidenced. Stable from 30 to 180 cm ([ZH19]); works on 60x36 px eye images ([ZH17]); 30x18 px eye crops performed in the same range as full face ([GU20]). | New person without calibration; glasses (2.8 to 4.5 degrees in [ZH19]); training and test resolution mismatch ([ZH17]); cross-dataset shift ([ZH17]). |
| Hybrid | Keep explicit geometry (head pose, gaze ray, screen intersection, personal offset) and learn the parts geometry gets wrong, or learn landmarks and reason geometrically on them ([GU20], [LI19], [CS20], [PA18]). | As appearance or landmarks, plus geometry. | A few points for a low-dimensional personal correction ([LI19], [CS20]). | 2.70 degrees on MPIIGaze with 9 calibration samples ([LI19]). 3.7 degrees with 1 sample, 2.7 to 3.0 degrees with 9 on MPIIGaze ([CS20], read from figure). 4.5 degrees PI on MPIIGaze via an intermediate geometric representation ([PZ18]). Screen mapping: geometric prior plus regression beat pure geometry and pure regression across calibration-set sizes ([GU20]). | Inherits from whichever part reads the eye: good if appearance, poor if landmarks. | Inherits both sets; fewer direct comparisons exist. |

## Family notes

### Geometric

- The visual axis is offset from the optical axis by about 4 to 5 degrees horizontally and 1.5 degrees vertically, varying up to 3 degrees between people ([HJ10]). It cannot be observed in the image ([PK20]). So an uncalibrated geometric model carries a bias of that order.
- Most 3D model-based methods need camera calibration and a geometric model of camera and monitor position ([HJ10]). MPIIGaze obtained screen pose with a mirror-based procedure and per-camera intrinsics ([ZH17]).
- [HJ10] reports 1 to 2 degrees for single-camera, no-light, fully calibrated iris-contour methods; the survey text ties these to a narrow field-of-view camera, that is a high-resolution eye. For web-camera methods it reports 2 to 4 degrees, and "about 5 degrees" for natural-light methods overall.
- In infrared trackers, free head movement with one camera relies on multiple corneal reflections ([GE06], abstract). A webcam has none, so head pose must come from face landmarks.
- Feature quality is the limit: with the same model, manual pupil annotation gave 2.5 degrees and the real-time detector 3.5 degrees ([WJ17]).
- Offset-only calibration helps little: a landmark-fitted eye model "only benefits initially and only marginally from calibration" ([PA18]).
- Sensitivity (derived from the sibling-ticket 0.5 px per degree): a 1 px error in iris centre relative to eyeball centre is about 2 degrees.

### Feature regression

- Geometry-free: the map absorbs camera, screen and personal parameters, at the price of several in-session points ([HJ10]).
- A fitted map is only valid near the head pose seen in calibration; classical 2D regression needs head-movement compensation or a fixed head ([HJ10]).
- Eye corners move slightly with gaze even with a static head, which caps the iris-centre-to-corner feature at 2 to 3 degrees ([SE12], abstract).
- Rich landmark sets from a learned detector fed to a small regressor beat network features at low calibration counts, converging only past 100 samples ([PA18]).

### Appearance-based

- Classical per-user models reached about 1 degree with many calibration samples; [HJ10] notes none had reported head-pose invariance by 2009.
- Sparse per-user regression was proposed to cut the number of calibration samples and tolerate slight head motion and resolution variation ([LU14], abstract; no figures in the abstract).
- Deep models trade calibration for training data: about 5 degrees cross-person versus about 3 degrees person-specific is the usual gap ([PK20]); 5.4 versus 2.5 degrees on MPIIGaze+ ([ZH17]).
- In-the-wild conditions cost accuracy even for person-specific models: 2.5 degrees on laptop data versus 0.9 degrees on controlled lab data ([ZH17]).
- Resolution: accuracy drops when test images are smaller than training images; higher resolution "does not always mean better" ([ZH17]).
- Temporal averaging lowers error (per-dot error below per-frame error, [KR16]).

### Hybrid

- Personal variation is low-dimensional: 3 parameters per eye sufficed, which the authors relate to the parameters of geometric eye models ([LI19]).
- A single calibration point fixes a constant angular bias; multi-point calibration gains about 0.2 degrees more, so the bias is not quite constant across gaze angles ([CS20]).
- For mapping gaze direction to the screen: pure geometry was best with about 9 or fewer points but stagnated; pure regression needed many points; geometry with a learned correction was best across the range; pure geometry degraded most with head movement ([GU20]).
- A learned 3D face-and-eye shape prior made a landmark-driven geometric model tolerant of free head movement at 3.5 degrees ([WJ17]).

## Personal calibration

What a few points buy (RGB, deep appearance or hybrid unless noted):

| Source | Setup | No calibration | With calibration |
|---|---|---|---|
| [ZH19] | 1080p webcam, 75 cm, 20 participants | 6.4 degrees | 2.5 degrees at 60 samples; "competitive" with a commercial infrared tracker from 4 samples; worse than uncalibrated at 1 sample (flexible map underdetermined) |
| [CS20] | MPIIGaze | 4.5 degrees | 3.7 (1 sample), 3.2 (4), 3.0 (9), 2.9 (16) at one gaze point; 2.9, 2.7, 2.7 with multiple points; floor 2.6 (read from figure) |
| [PA19] | MPIIGaze; GazeCapture | not comparable | 3.42 and 3.18 degrees with 3 samples; 3.14 degrees on MPIIGaze with 9 |
| [LI19] | MPIIGaze | not comparable | 2.70 degrees with 9 samples; little gain beyond 3 personal parameters |
| [ZH17] | MPIIGaze+ | 5.4 degrees | 2.5 degrees with 2,500 images per person |
| [PA18] | MPIIGaze+, landmark regression | 5.5 degrees (prior PI result) | 4.6 degrees with 20 samples |
| [KR16] | Phones; tablets | 1.71 cm; 2.53 cm | 1.34 cm; 2.12 cm with 13 points; 4 points made it worse |
| [VL20] | Phone on stand, 25 to 40 cm, near-frontal head, 26 participants | 1.92 cm | 0.46 cm (0.6 to 1 degree) with about 100 frames, under 30 s |

Findings:

- For a person-independent estimator the between-person bias exceeds the within-person variance ([CS20]); 1 to 4 points remove most of the achievable gain ([CS20], [ZH19]).
- Returns flatten after about 9 points: 2.7 degrees with 9 to 16 samples versus 2.5 degrees with 2,500 on MPIIGaze ([LI19], [CS20], [ZH17]).
- Fewer parameters than points: a flexible correction with too few points overfits ([ZH19], [KR16]). Low-dimensional corrections are robust at 1 to 9 points ([CS20], [LI19]).
- The 0.6 to 1 degree phone result used a larger eye image (25 to 40 cm) and a near-frontal, stand-mounted setup; the authors report accuracy decaying with distance and head rotation ([VL20]).
- A 5-minute calibration over 7 head poses, a virtual chin rest and 7-point recalibration every few trials gave 1.4 degrees accuracy and 1.1 degrees precision at 60 cm with a 1080p webcam, 19 participants ([KA23]). Precision is otherwise rarely reported.

Implicit calibration:

- Premise: gaze is near the cursor at a click. Median gaze-to-click distance 74 px on a 17 inch 1280x1024 display, where 16 px was 0.5 degree, so about 2.3 degrees (derived) ([HW12]). A later study found a mean of 137 px on denser displays ([PP18]). Click labels are therefore noisy at the 2 degree level.
- Click-trained regression from eye pixels: 4.17 degrees, chin rest, 59 cm, 1080p webcam, 4 participants; 175 to 210 px in an online study ([PP16]).
- Click-trained appearance model with head-pose clustering: 2.9 degrees, desktop, real-world environments ([SU15], abstract).
- Interaction-trained model with validated samples: 2.56 degrees in situ ([HU16], abstract).
- Saliency of watched video as a weak label: 3.5 degrees ([SU13], abstract).
- Screen content used to refine a network's estimate without labels: 3.48 to 2.49 degrees on the EVE dataset ([PK20]).
- Reading: implicit signals reach 2.5 to 4 degrees and suit drift correction and accumulation over a session; they have not been shown to beat explicit points.

## Single user, single laptop, per-session calibration

- No peer-reviewed result was found for exactly this setup. Closest conditions: laptop webcams in daily use ([ZH17]); 1080p external webcam with up to 60 calibration clicks ([ZH19]); few-shot personalisation on laptop data ([PA19], [LI19], [CS20]).
- Evidenced range with natural head movement and a short calibration: 2.5 to 3.2 degrees ([ZH19], [ZH17], [LI19], [CS20]). At 55 cm, 1 degree is 0.96 cm on screen (trigonometry), so 2.4 to 3.1 cm.
- About 1 to 1.4 degrees needed head restraint, long calibration or frequent recalibration ([XU15], [KA23]). Below 1 degree is evidenced on phones at 25 to 40 cm ([VL20]), with infrared hardware ([ZH19], [LI19]) and for classical appearance methods without head-pose invariance ([HJ10]).
- One fixed user and device removes cross-person and cross-device error, the largest terms ([ZH17]). Session-to-session change (illumination, seating) remains, which is what per-session calibration addresses; in-the-wild data stayed at 2.5 degrees even person-specific ([ZH17]).
- On the owner's geometric hypothesis: as the sole estimator with offset-only calibration it is the weakest evidenced option on webcam-resolution eyes ([ZH19], [PA18], [WJ17]). As a prior it is supported: geometry handles head movement and sparse calibration, a learned correction removes its bias ([GU20], [LI19], [WJ17]).
- Best-supported directions, in order of evidence: (1) per-user calibrated regression on learned eye appearance or dense landmarks, with head-pose compensation; (2) geometric head-pose and screen model with a low-dimensional learned personal correction; (3) pure geometric eye model.
- Eye region at the target distance: an iris of about 29 px implies an eye crop of very roughly 60 to 75 px wide (unverified estimate), the same order as the 60x36 px inputs of [ZH17].

## Not verified

- [HJ10] was read from the authors' draft dated 23 January 2009, not the published version.
- Abstract only: [WB14], [SE12], [VA12], [LU14], [HU16], [SU15], [SU13], [GE06]. Their conditions (head movement, distance, camera) are not confirmed beyond the abstract.
- [CH24] table 5: values were read from extracted text; column assignment for MPIIFaceGaze is likely but not checked against the typeset table.
- [CS20] per-sample values were read from figure annotations; the 16-sample figures agree with the text.
- [ZH19] and [WJ17] do not state how much participants moved during testing beyond "stand or sit" and the reported translation ranges.
- [KA23] evaluates a commercial system; independence of the authors from the vendor is unverified.
- Sibling-ticket figures (29 px iris, 0.5 px per degree, 70 degree field of view) were taken as given.
- No source found for: built-in laptop camera at 50 to 60 cm with calibration of 30 s or less and natural head movement; precision in degrees for most methods.

## Sources

- [HJ10] Hansen, Ji. In the Eye of the Beholder: A Survey of Models for Eyes and Gaze. IEEE TPAMI 32(3), 2010. https://doi.org/10.1109/TPAMI.2009.30 (draft read: https://people.ict.usc.edu/~gratch/CSCI534/Old-Readings/WitznerJi_EyeTrackSurvey(2009).pdf)
- [CH24] Cheng, Wang, Bao, Lu. Appearance-based Gaze Estimation With Deep Learning: A Review and Benchmark. IEEE TPAMI, 2024. https://arxiv.org/abs/2104.12668
- [ZH19] Zhang, Sugano, Bulling. Evaluation of Appearance-Based Methods and Implications for Gaze-Based Applications. CHI 2019. https://arxiv.org/abs/1901.10906
- [ZH17] Zhang, Sugano, Fritz, Bulling. MPIIGaze: Real-World Dataset and Deep Appearance-Based Gaze Estimation. 2017. https://arxiv.org/abs/1711.09017
- [KR16] Krafka et al. Eye Tracking for Everyone. CVPR 2016. https://arxiv.org/abs/1606.05814
- [PA19] Park et al. Few-Shot Adaptive Gaze Estimation. ICCV 2019. https://arxiv.org/abs/1905.01941
- [LI19] Lindén, Sjöstrand, Proutiere. Learning to Personalize in Appearance-Based Gaze Tracking. 2019. https://arxiv.org/abs/1807.00664
- [CS20] Chen, Shi. Offset Calibration for Appearance-Based Gaze Estimation via Gaze Decomposition. 2020. https://arxiv.org/abs/1905.04451
- [PA18] Park, Zhang, Bulling, Hilliges. Learning to Find Eye Region Landmarks for Remote Gaze Estimation in Unconstrained Settings. ETRA 2018. https://arxiv.org/abs/1805.04771
- [PZ18] Park, Spurr, Hilliges. Deep Pictorial Gaze Estimation. 2018. https://arxiv.org/abs/1807.10002
- [WJ17] Wang, Ji. Real Time Eye Gaze Tracking with 3D Deformable Eye-Face Model. ICCV 2017. https://openaccess.thecvf.com/content_ICCV_2017/papers/Wang_Real_Time_Eye_ICCV_2017_paper.pdf
- [WB14] Wood, Bulling. EyeTab: Model-based Gaze Estimation on Unmodified Tablet Computers. ETRA 2014. https://doi.org/10.1145/2578153.2578185
- [SE12] Sesma, Villanueva, Cabeza. Evaluation of Pupil Center-Eye Corner Vector for Gaze Estimation Using a Web Cam. ETRA 2012. https://doi.org/10.1145/2168556.2168598
- [VA12] Valenti, Sebe, Gevers. Combining Head Pose and Eye Location Information for Gaze Estimation. IEEE TIP, 2012. https://doi.org/10.1109/TIP.2011.2162740
- [LU14] Lu, Sugano, Okabe, Sato. Adaptive Linear Regression for Appearance-Based Gaze Estimation. IEEE TPAMI, 2014. https://doi.org/10.1109/TPAMI.2014.2313123
- [XU15] Xu et al. TurkerGaze: Crowdsourcing Saliency with Webcam based Eye Tracking. 2015. https://arxiv.org/abs/1504.06755
- [GU20] Gudi, Li, van Gemert. Efficiency in Real-time Webcam Gaze Tracking. 2020. https://arxiv.org/abs/2009.01270
- [PK20] Park et al. Towards End-to-end Video-based Eye-Tracking. ECCV 2020. https://arxiv.org/abs/2007.13120
- [VL20] Valliappan et al. Accelerating eye movement research via accurate and affordable smartphone eye tracking. Nature Communications 11, 2020. https://doi.org/10.1038/s41467-020-18360-5
- [KA23] Kaduk, Goeke, Finger, König. Webcam eye tracking close to laboratory standards: Comparing a new webcam-based system and the EyeLink 1000. Behavior Research Methods, 2023. https://doi.org/10.3758/s13428-023-02237-8
- [PP16] Papoutsaki et al. WebGazer: Scalable Webcam Eye Tracking Using User Interactions. IJCAI 2016. https://www.ijcai.org/Proceedings/16/Papers/540.pdf
- [PP18] Papoutsaki et al. The Eye of the Typer: A Benchmark and Analysis of Gaze Behavior During Typing. ETRA 2018. https://jeffhuang.com/papers/EyeTyper_ETRA18.pdf
- [HW12] Huang, White, Buscher. User See, User Point: Gaze and Cursor Alignment in Web Search. CHI 2012. https://jeffhuang.com/papers/GazeCursor_CHI12.pdf
- [HU16] Huang, Kwok, Ngai, Chan, Leong. Building a Personalized, Auto-Calibrating Eye Tracker from User Interactions. CHI 2016. https://doi.org/10.1145/2858036.2858404
- [SU15] Sugano, Matsushita, Sato, Koike. Appearance-Based Gaze Estimation With Online Calibration From Mouse Operations. IEEE THMS, 2015. https://doi.org/10.1109/THMS.2015.2400434
- [SU13] Sugano, Matsushita, Sato. Appearance-Based Gaze Estimation Using Visual Saliency. IEEE TPAMI, 2013. https://doi.org/10.1109/TPAMI.2012.101
- [GE06] Guestrin, Eizenman. General Theory of Remote Gaze Estimation Using the Pupil Center and Corneal Reflections. IEEE TBME, 2006. https://doi.org/10.1109/TBME.2005.863952

[HJ10]: https://doi.org/10.1109/TPAMI.2009.30
[CH24]: https://arxiv.org/abs/2104.12668
[ZH19]: https://arxiv.org/abs/1901.10906
[ZH17]: https://arxiv.org/abs/1711.09017
[KR16]: https://arxiv.org/abs/1606.05814
[PA19]: https://arxiv.org/abs/1905.01941
[LI19]: https://arxiv.org/abs/1807.00664
[CS20]: https://arxiv.org/abs/1905.04451
[PA18]: https://arxiv.org/abs/1805.04771
[PZ18]: https://arxiv.org/abs/1807.10002
[WJ17]: https://openaccess.thecvf.com/content_ICCV_2017/papers/Wang_Real_Time_Eye_ICCV_2017_paper.pdf
[WB14]: https://doi.org/10.1145/2578153.2578185
[SE12]: https://doi.org/10.1145/2168556.2168598
[VA12]: https://doi.org/10.1109/TIP.2011.2162740
[LU14]: https://doi.org/10.1109/TPAMI.2014.2313123
[XU15]: https://arxiv.org/abs/1504.06755
[GU20]: https://arxiv.org/abs/2009.01270
[PK20]: https://arxiv.org/abs/2007.13120
[VL20]: https://doi.org/10.1038/s41467-020-18360-5
[KA23]: https://doi.org/10.3758/s13428-023-02237-8
[PP16]: https://www.ijcai.org/Proceedings/16/Papers/540.pdf
[PP18]: https://jeffhuang.com/papers/EyeTyper_ETRA18.pdf
[HW12]: https://jeffhuang.com/papers/GazeCursor_CHI12.pdf
[HU16]: https://doi.org/10.1145/2858036.2858404
[SU15]: https://doi.org/10.1109/THMS.2015.2400434
[SU13]: https://doi.org/10.1109/TPAMI.2012.101
[GE06]: https://doi.org/10.1109/TBME.2005.863952
