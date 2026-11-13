# Landing on hit targets smaller than gaze accuracy

Research for #19. Sources read 2026-11-13.

Labels:

- **paper**: read in the full text of the cited source. Default when no label is given.
- **abstract**: read in the abstract only.
- **derived**: computed here from figures the source states. The arithmetic is shown or obvious.
- **unverified**: not read in a primary source. Repeated in [Not verified](#not-verified).

"Device" below means the commercial infrared eye tracker a study used; "estimator" is this project's. Sizes in degrees are the source's own unless marked derived. A 24 pt square is 0.5 deg at 55 cm: a cursor within 0.25 deg of its centre is always inside, one beyond 0.35 deg never is (derived).

## Answer

- One study measured head movement refining gaze on a desktop near the required size: Look and Lean [LL14]. Experienced users, device offset about 0.5 deg, key press: within 0.25 deg of centre on 76.1% of valid presses, within 0.38 deg on 90.8%, within 0.5 deg on 96.2%, in 1.54 s; 9.8% of trials were invalid, 9.5% for no press inside 2.5 s. Gaze alone: 18.0%, 35.3%, 54.1% in 1.17 s.
- No study found drives both gaze and head from one webcam. HMAGIC [HM15] used a webcam for the head and an infrared device for gaze, and names the single-camera version as future work.
- Best published case for head refinement, headset head pose sensed by the headset: after a gaze jump, mean offset 0.49 deg (from 2.42 deg); the hit target that holds 95% of landings is 1.98 x 3.95 deg. Head refining head: 0.58 x 1.10 deg [PP18]. Neither reaches a 0.5 deg square at 95%.
- Time cost of head refinement: under 0.4 s on a 0.5 deg starting offset [LL14]; 0.65 to 0.75 s in head mode with offsets up to 5 deg, total 1.44 to 1.66 s on 3 deg hit targets [BG20]. Both report the cost growing with the starting offset.
- Five ways deliberate head movement was told from natural: not at all (head offset always applied) [LL14]; a pointer-speed and direction rule [HM15]; a held button [PP18]; fixed thresholds on eye and head velocity, timing and direction [BG20]; a learned classifier, F1 0.89 against 0.62 for the thresholds [HB23].
- Magnification with two looks and a key hold: 0.67 deg hit targets in 1.26 to 1.62 s with 18 to 24% misses; mouse 1.23 s, 2% [EP07].
- Target-aware mechanisms need the rectangles of the hit targets on screen. With them: 3.5% misses at 1.46 s median on web links [AG15]; under 10% misses on 0.35 deg hit targets given three times the width in free space, with a dwell of 750 ms or more [MI04].
- Head-only pointing through a webcam: 1.28 to 1.43 bits/s, 2.2 to 2.6 s per hit target of about 0.8 to 1.3 deg, 8 to 11% misses [MA15]. That is above the 2 s requirement. Adding a gaze jump raised pointer speed 1.6 to 1.9 times in HMAGIC [HM15] (derived).
- No published figure was found for the precision of webcam head pose while still, in degrees or millimetres, for MediaPipe or any landmark model. Accuracy against motion capture: MediaPipe Face Mesh off by 11.0 deg yaw, 7.0 deg pitch, 1.4 deg roll at the end of 25 to 60 deg movements, one participant [HA22]. One comparison found the tracked nose position steadier than estimated pitch and yaw [CM17].
- macOS Head Pointer has two modes: a joystick mode driven by where the face is turned, with a dead zone, and a mouse-like mode driven by head movement. One speed setting. Apple documents no accuracy, latency or gain [AP-pc].

## Head movement refining gaze

| Study | Setup | Hit target | Time to land | Miss rate | Gaze accuracy | Head sensing and mapping |
|---|---|---|---|---|---|---|
| Look and Lean [LL14], ETRA 2014 | Desktop. Tobii T60, 60 Hz, 17 in 1280x1024, about 60 cm. 9 participants experienced in gaze pointing. Key press. Hit target shown 2.5 s. | 10 px dot in a 45 px square. Scored as share of presses within radius R of the centre. 1 deg = 39.8 px (derived from 17 in, 5:4, 60 cm). | With head 1541 ms (SD 161), gaze only 1170 ms (SD 284), separate blocks. Mixed blind trials: 1463 vs 1631 ms. | With head / gaze only, valid trials: R 10 px (0.25 deg) 76.1% / 18.0% inside; 15 px (0.38 deg) 90.8% / 35.3%; 20 px (0.50 deg) 96.2% / 54.1%. Invalid trials 9.8% / 2% (no press in 2.5 s: 9.5% / 1.8%). | Not stated. Gaze-only mean distance to centre 20.3 px, 0.51 deg (derived); with head 8.0 px, 0.20 deg. | Eye position in the device's camera image, no extra sensor. Linear: about 15 px of cursor per 1 cm of lateral head translation, 0.38 deg/cm (derived). Left-right translation for x, pitch for y. |
| HMAGIC [HM15], PETRA 2015 | Desktop. 19 in 1024x768, about 60 cm. EyeTribe (remote) or Pupil Pro (head-mounted). 7 participants. Dwell 750 ms. | Circles 50 and 100 px, "approximately 2 and 4 cm": 1.9 and 3.8 deg (derived). Distances 300 and 500 px. | Reported as pointer speed, dwell excluded. Head only 231 to 365 px/s; with remote device 407 to 650; with head-mounted 365 to 595. | Counted, not reported. | Not measured. States 0.5 to 1 deg as typical. | Webcam (Logitech QuickCam Pro 9000) tracking the nose tip. Pointer = reference + gain x feature displacement in camera coordinates, separate x and y gains, values not stated. Gaze moves the reference. |
| Pinpointing [PP18], CHI 2018 | HoloLens with Pupil Labs device, 120 Hz, right eye. Hit targets on a wall at 2 m, 7 and 21 deg out. 12 participants. Button. 5 s limit. | A point (cross). Reported as mean offset and as the size holding 95% of landings. | Eye only 1.38 s, head only 2.30 s. Refined times in a figure only. | 86.4% of all trials counted as successful (5 s limit, 2 deg distance limit at selection). | Eye only: mean offset 2.42 deg (SD 1.27). | Headset head pose. Eye then head: 0.49 deg mean offset, 95% size 1.98 x 3.95 deg. Head then head: below 0.2 deg, 0.58 x 1.10 deg. Head only: 0.32 deg, 2.20 x 2.08 deg. Refinement at "CD ratio 2:1" against 1:1 for head pointing. |
| BimodalGaze [BG20], ETRA 2020 | VR. HTC Vive with Tobii device, 120 Hz. 12 participants. Controller button. Offsets from three distributions between 0 and 5 deg injected. | Spheres 3 deg across at 10, 25, 40 deg. | Trials that used head mode: 1.66 s (SD 0.95) automatic switch; 1.44 s (SD 0.56) button switch. In head mode: 0.65 s and 0.75 s. | First press off the hit target, head mode: 7.2% automatic, 5.8% button. | 0.98 deg (SD 0.23), precision 0.43 deg, before the injected offset. | Headset orientation. Cursor follows the head in head mode. |
| MAGIC pointing for eyewear [JA15], ISWC 2015 | Eyewear computer (abstract); Google Glass according to [PP18]. | Not in abstract. | "Faster than head pointing for far targets" (abstract). | Not in abstract. | "More accurate than eye pointing" (abstract). | Not in abstract. [PP18] reports it used a 1:1 ratio and matched head-only accuracy. |

For reference, the origin of the cascade is MAGIC pointing [MG99], CHI 1999: gaze places the cursor, the hand refines. The paper's full text was not obtained. The authors' talk slides state: hit targets 20 and 60 px, distances 200 to 800 px, 12 participants, device "error: 1 degree or more", "delay: 66 ms or more"; throughput 3.2 bits/s manual, 4.5 conservative (cursor jumps when the hand device moves), 4.7 liberal (cursor jumps on every large saccade) [MG99-slides].

Notes on [LL14]:

- Hit rates exclude invalid trials. Counting timeouts as misses, the with-head rate at 0.5 deg radius is about 0.962 x 0.902 = 87% (derived).
- "The time cost of the cursor location correction by head movements was less than 400 ms on average. The duration increases as the inaccuracy of the tracker data increases."
- Gain is what the offset demands of the body: at 0.38 deg/cm, a 1.5 deg offset needs about 4 cm of head translation, 3 deg about 8 cm (derived).
- Gaze was smoothed over a 500 ms window (about 30 samples) so the cursor held still enough to correct.
- Central versus peripheral hit targets: 7.5 vs 9.1 px with head, 17.8 vs 22.2 px without; neither difference significant.
- Novices not told about the head mechanism did not find it in a 4 to 5 minute block: 16.2 vs 20.6 px, not significant.
- With the mechanism switched off, 3 of 10 participants still landed as well by moving the head (11.8 px off, 11.5 px on): head movement alone shifted the device's point of gaze for them. Unexplained by the authors.
- Head rotation (yaw) "often caused eye losses" for participants with glasses; leaning forward or back degraded the gaze data. Both are properties of that infrared device.
- The authors recommend a selection that fires while the cursor passes over the hit target (key, not dwell).

### Telling deliberate from natural head movement

| Study | Rule |
|---|---|
| [LL14] | None. The head offset from a reference is always added to the gaze cursor. Reference = eye position in the camera at the first valid sample; the authors call for a command to reset it because the neutral position drifts. Pilot: saccades across the screen changed the eye position in the camera "much" less than "tiny head movements", so no eye-movement filter was used. Suggested, not built: accept adjustments only while gaze is stable. |
| [HM15] | The head always drives the pointer. Gaze moves it only when the head-driven pointer is faster than 30 px/s, the point of gaze lies within 90 deg of its direction of travel, and the pointer is outside a region around the point of gaze. Inside the region the head keeps control. Region size not stated. |
| [PP18] | Explicit. Holding a button starts head refinement, release selects. Participants in [BG20] reported pressing too early, while the head was still finishing the gaze shift, which dragged the cursor off. |
| [BG20] | Automatic. Two criteria mark head movement as natural: it starts within 150 ms of an eye movement; it travels within 20 deg of that eye movement's direction. Movement classed as gestural switches the cursor to the head. Head movement counts above 15 deg/s. Switching is suppressed while gaze moves faster than 160 deg/s, set high so corrective saccades, the vestibulo-ocular reflex and pursuit do not switch back. Back to gaze when cursor and gaze are more than 10 deg apart. |
| [HB23] | Learned classifier (gradient-boosted trees) on head and eye signals from a VR headset, 512 ms feature window, 1024 ms history. F1 0.89 user-independent; the [BG20] thresholds scored 0.62 on the same data (precision 0.71, recall 0.58). It found gesture onset 119 ms earlier on average. |

What the same sources report about the behaviour:

- [BG20]: 82.5% of selections ended in head mode. 54.4% of misses happened in gaze mode: the cursor crossed the hit target during the saccade's over- or undershoot and the press came before gaze settled. The 15 deg/s threshold missed small corrections; users then exaggerated the movement and overshot. Users paused to judge the cursor before a gestural movement and "very rarely" passed from natural to gestural within one head movement.
- [BG20] thresholds come from VR data: head movement generally starts 150 ms after the eye movement, and in 90% of gaze shifts with head movement the two directions differ by less than 20 deg.
- [HB23]: with a fixed head-velocity threshold, movement that stayed below 15 deg/s was always called natural. Smallest controllable gestural head rotation 0.3 deg, largest comfortable 40 deg (headset).
- [ST99] (abstract): the range of gaze shifts made with the eyes alone was 35.8 deg wide on average, SD 31.9 deg, stable per person across sessions. This project's screen spans about 31 x 20 deg at 55 cm (derived), so whether a gaze shift across it brings the head along depends on the person.
- After the eyes land, the head typically keeps moving while the eyes counter-rotate (vestibulo-ocular reflex) [BG20, citing the eye-head coordination literature].

## Magnification and two-step selection

| Study | Mechanism | Hit target | Time to land | Miss rate | Device |
|---|---|---|---|---|---|
| EyePoint [EP07], CHI 2007 | Look, hold a key: a 120 px square around the point of gaze appears magnified 4x. Look again, release. 20 participants. | 22, 30, 40 px squares: 0.67, 0.9, 1.2 deg (derived from the paper's 33 px per degree). | 22 px: 1256 to 1619 ms across three variants; mouse 1233 ms. Web links: 1915 ms; mouse 1576 ms. | 22 px: 18 to 24%; 30 px: 17 to 18%; 40 px: 12 to 15%; mouse 2%, 2%, 1%. Web links 13%; mouse 3%. | Tobii 1750. States 0.5 to 1 deg as the state of the art. |
| Zooming interface [BI04] reporting [BI02] | Whole-screen zoom under switch control. 6 participants. | 0.3, 0.6, 0.9, 1.2 deg. | Not in the summary read. | Not in the summary read. Without zoom, task efficiency 18% at 0.3 deg. | Not stated for the 2D experiment. |
| Fisheye lens [AS05], GI 2005 | Lens magnifies 3x around the point of gaze. Two variants show it only once a fixation starts (one then follows gaze, one stays put). Dwell 500 ms. 9 participants analysed. | 34 x 27 px, 1.3 deg diagonal, at 50 cm. | 3359 and 3393 ms for the two fixation-triggered variants; 4846 ms no lens; 4801 ms lens always on. | Wrong or aborted trials 12 to 23%, no significant difference between conditions. | Tobii ET-1750, 0.5 deg. |

- [EP07]: miss rate was about 10% for participants the device worked well for and about 33% for the others. Many misses in the rapid task were key presses made before gaze reached the hit target. The second look costs a second visual search in the magnified view. A cursor showing the point of gaze in the magnified view slowed users and was turned off by default.
- [BI04]: given control of the zoom, users stopped when the hit target subtended 1.6 to 1.8 deg, whatever its original size.
- [LL14], citing Skovsgaard et al. 2010: zooming "can dramatically slow down the interaction". Skovsgaard not read: unverified.

## Snapping and target-aware mechanisms

| Study | Must know about the screen | Hit target | Time to land | Miss rate | Device |
|---|---|---|---|---|---|
| Expansion in motor space [MI04], CHI 2004 | Rectangle of each hit target, and free space around it: the active area is enlarged invisibly. A dwell that tolerates brief exits ("grab-and-hold"). | 12, 24, 36 px wide: 0.35, 0.7, 1.05 deg at 70 cm. | 1672 ms grand mean, including dwell of 750 to 1250 ms. | 9.9% grand mean. At 1250 ms dwell: 10.9% with grab-and-hold, 25.6% without. Under 10% for the 12 px hit target with 3x expansion. | EyeLink (SMI). |
| Expanding menu items [SM05], ICMI 2005 | Menu geometry, and control of its layout: the candidate item grows, and the gaze shift that follows corrects the calibration. | Items 20 px high, 0.6 deg at 70 cm. | 39% slower than without (abstract). | 9.2% with; 55.3% without; mouse 3.8%. | SMI iView X. |
| Gaze plus speech [MI06], ETRA 2006 | Rectangles of the hit targets near the point of gaze: each gets a colour, the user says the colour. Needs a microphone. | 20, 30, 40 px squares, gaps 0 to 20 px, at 70 cm; the abstract gives the largest as 0.85 deg. | 2609 ms with speech; 3449 ms gaze-only dwell. Dwell 1000 to 2000 ms. | 17.4% with speech; 51.1% gaze-only dwell. Best about 93% correct at 0.85 deg with 0.3 deg gaps (abstract). | SMI iView X. |
| Actigaze [AG15], UIST 2015 | Position of every clickable element (web page links). Links near the point of gaze, within about 1 cm, are coloured; the user dwells on a fixed button of the same colour at the screen edge. | Wikipedia text links, "medium font size"; size in degrees not given. 23 in screen. | Median 1.46 s (all links coloured), 1.67 s (coloured on dwell); mouse 1.1 s. | 3.5%, 2.1%; mouse 1.9%. | Tobii X2-30. 25 participants, most new to eye trackers. |

- All four select among known hit targets; none places a cursor at an arbitrary point. The requirement's hit target is "anywhere on screen", so each needs the hit target rectangles from the system (accessibility tree or page structure). Whether macOS exposes them for arbitrary applications was not researched here.
- [MI06]: side-by-side hit targets (no gap) were markedly worse; 10 px and 20 px gaps did not differ.
- Baseline these papers share: gaze alone with dwell on hit targets of 0.35 to 0.85 deg misses 25 to 55% of the time [MI04], [SM05], [MI06].
- Not read: Zhang, Ren, Zha 2008 (force field, speed reduction, warp to the hit target's centre, as [LL14] describes it); Salvucci and Anderson 2000 (probabilistic assignment of gaze to interface objects); Grossman and Balakrishnan 2005 (bubble cursor, a mouse technique). Unverified.

## Head-only pointing with a camera

| Study | Sensing | Hit target | Time to land | Miss rate | Throughput |
|---|---|---|---|---|---|
| Camera Mouse [MA15], HCII 2015 | Logitech C920 webcam, tracked face feature. 13 in 1366x768 at about 2.5 ft. 10 participants. | Circles 50 and 80 px: about 0.8 and 1.3 deg (derived). Distances 300, 600 px. | 2226 ms with a muscle-switch click; 2609 ms with 1 s dwell. Touchpad 1302 ms. | 10.8%; 8.1%. Touchpad 3.8%. | 1.43; 1.28 bits/s. Touchpad 2.10. |
| HMAGIC head-only condition [HM15] | Webcam, nose tip. | 1.9 and 3.8 deg (derived). | 231 to 365 px/s. A 300 px move to the small hit target at 231 px/s is 1.3 s before the 750 ms dwell (derived). | Not reported. | Not reported. |
| Head tracking on a tablet [RM18], IJHCS 2018 | iPad Air front camera. 12 participants. | 130 and 260 px at 264 ppi: 12.5 and 25 mm (derived). Viewing distance not given. | 1.65 s grand mean. | 8.5% grand mean. | 1.42 bits/s. |
| FittsFace [CM17], HCII 2017 | Nexus 7 front camera, vendor face-tracking interface. 12 participants. | 60 and 100 (units as in paper), distances 250, 500. | 7.1 s grand mean. | 16.6% grand mean. | 0.58 bits/s from nose position; 0.36 from face pitch and yaw. |
| Camera Mouse [BE02], [GI00] | 15 x 15 px template of a face feature matched in 320x240 frames at 30 Hz. Gain adjustable. | Dwell click needs the pointer inside a 30 px radius for 0.5 s. | About 2 s per character on an on-screen keyboard: 1.5 s to move, 0.5 s dwell [GI00]. | Not reported. | Not reported. |

Head pointing sensed by a headset, not a camera, as an upper reference:

- [MK19]: 3.40 bits/s head, 3.87 mouse, 2.55 gaze; hit targets 3.1 and 4.7 deg; 27 participants.
- [PP18]: head only lands 0.32 deg from a point on average in 2.30 s; 95% size 2.20 x 2.08 deg.
- [QT17] (VR, hit targets as spheres): miss rate roughly 8% head only, 40% eye only, 30% eye plus head.
- [MK19] cites 2.0 bits/s for a head tracker (De Silva et al. 2003); [CM17] cites 1.61 bits/s for a laptop webcam tracking a head-worn marker. Neither source read: unverified.

## What a webcam resolves of head pose

Published evaluations found:

| Source | What was measured | Result |
|---|---|---|
| [HA22], Sensors 2022 | Head angles from RGB video against optical motion capture. One participant, camera at 1 m, movements to about 25 or 60 deg. MediaPipe Face Mesh landmarks with a perspective-n-point solve. | Offset at the end of the movement, mean (SD): yaw 11.00 (10.65) deg, pitch 7.00 (10.22) deg, roll 1.37 (2.44) deg. OpenFace 2.0: 12.37, 14.12, -0.75 deg. 3DDFA_V2: -5.62, 0.87, -0.37 deg. MediaPipe exceeded 10 deg beyond about 35 deg of pitch. |
| [KA19], Face Mesh paper | Landmark position against human annotation, normalised by interocular distance. | 3.96% (full model); two human annotators differ by 2.56%. A temporal filter is applied so that landmarks show no "visible jitter"; no figure given. |
| [HE22], 6DRepNet | Learned head rotation from one RGB image, benchmark datasets, many people, wide pose range. | Mean absolute offset 3.47 deg (BIWI), 3.97 deg (AFLW2000); 2.66 deg when trained on part of BIWI. |
| [CM17] | Pointing with a tablet camera, nose position against estimated pitch and yaw. | Pitch and yaw values "noisier" than the nose position; 0.36 vs 0.58 bits/s. |
| [LL14] | Eye position in an infrared device's camera image, head still. | "Highly precise", "very minor fluctuation"; no figure. |

What follows:

- These are accuracy figures over large rotations and across people. Refinement needs something else: the precision of a small relative movement by one person near frontal. No published figure for that was found, for rotation or translation, for MediaPipe or any other landmark model. No published accuracy of head translation in millimetres from an RGB camera was found either.
- The two working desktop mechanisms did not estimate head pose at all. [LL14] and [HM15] map the image position of one feature (eye, nose tip) straight to a cursor offset through a gain. Image position is the quantity [CM17] found steadier.
- Scale, derived, resting on an unverified field of view: the physical-limits note assumes 2.49 camera px per mm at the face. At that scale 1 cm of head translation is about 25 camera px. At the [LL14] gain (0.38 deg/cm, 18 pt/cm on this screen) one camera px is 0.7 pt of cursor; the 24 pt hit target is then about 33 camera px wide. At four times that gain it is about 8 px wide.

## macOS Head Pointer

From the Mac User Guide for macOS Sequoia 15 [AP-hp], [AP-pc]. Location: System Settings > Accessibility > Motor > Pointer Control > "Head pointer". The guide for macOS 15 does not use the label "Alternate Control Methods" on these pages.

- **What it tracks.** "the movement of your face or head, as detected by the camera that's built into or connected to your Mac". No other detail on the method.
- **Modes** ("Pointer moves"):
  - "When facing screen edges": "the pointer follows the direction in which you turn your face away from the center of the screen, similar to how you move a joystick. To stop the pointer, turn your face to the center of the screen again."
  - "Relative to head": "the pointer follows the direction in which you move your head (regardless of where your face is turned), similar to how you move a mouse. To stop the pointer, stop moving your head."
- **Speed.** "Pointer speed": "the lower the number, the slower the pointer moves". Also: "The farther you turn your face to the right or the faster you move your head, the faster the pointer moves", and at lower speed "the less distance the pointer moves when you move your face or head". No units or gain values.
- **Dead zone.** "Distance to edge", for the screen-edges mode only: "how far your face must be turned away from the center of the screen before the pointer starts moving. Set a higher number to help the camera differentiate between intentional and accidental movements."
- **Camera.** "Camera Options" picks the camera; the same camera serves facial-expression actions.
- **Pause and recalibrate.** A switch or facial expression can pause or resume. Recalibration repositions "the pointer in the middle of the screen" and resets "your default face or head position", after a 3 s countdown during which the user holds still.
- **Clicks.** Not part of Head Pointer: Mouse Keys, switches (keys, assistive switches, facial expressions such as a smile or open mouth, at Slight, Default or Exaggerated expressiveness), or Voice Control.
- **Coexistence.** "If you or someone else is moving the pointer using a mouse or trackpad, head pointer pauses; when you stop using the mouse or trackpad, head pointer automatically resumes."
- **Failure modes Apple lists.** Erratic pointer: lighting. Pointer stuck on an edge: user not centred. "Head pointer failed": too bright or dark, too close or far, not centred.
- Not documented: accuracy, precision, latency, frame rate, the smallest hit target it can land on, how the mouse-like mode separates head translation from rotation.

## Against the requirement

All derived; none of this was measured on this project's setup.

- The requirement is a 0.5 deg square, 95%, 2 s. The closest published result, [LL14], is 76 to 91% inside the equivalent radii (0.25 to 0.38 deg) at 1.54 s, with a further 9.5% of trials running past 2.5 s.
- [LL14] started from a gaze offset near 0.5 deg. This project's estimator requirement is 1.5 deg median, 3 deg at p90: three to six times the distance to correct. [LL14] and [BG20] both report refinement time rising with the offset.
- [LL14] states the gaze cursor must be "relatively stable" for head correction to be feasible, and smoothed it over 500 ms. The estimator's precision requirement is 0.5 deg STD, equal to the hit target's width.
- Headset head pose with 2:1 scaling held 95% of gaze-then-head landings inside 1.98 x 3.95 deg, and head-then-head inside 0.58 x 1.10 deg [PP18].
- Head-only webcam pointing is measured at 2.2 s and up for 0.8 to 1.3 deg hit targets [MA15]. The cascade's speed gain comes from the gaze jump [HM15].

## Not verified

- **MAGIC [MG99]**: full text not obtained (publisher blocked the download). Figures above are from the authors' slides. Participant count, completion times and miss rates in the paper itself: unverified.
- **[JA15]**: abstract only. Hit target sizes, times, head sensing: unverified. The 1:1 ratio and Google Glass are [PP18]'s description of it.
- **[BI02]** and Bates and Istance 2003 (head mouse versus eye mouse): not read. [BI04] is the same authors' summary of [BI02]. The claim that head pointing was more accurate and eye pointing faster comes from [LL14] and [BG20] citing the 2003 paper: unverified.
- **Skovsgaard et al. 2010, Lankford 2000** (zoom tools): not read. Unverified.
- **Zhang, Ren, Zha 2008; Salvucci and Anderson 2000; Grossman and Balakrishnan 2005**: not read. No numbers reported here. Unverified.
- **De Silva et al. 2003 (2.0 bits/s); MarkerMouse (1.61 bits/s)**: read only as citations in [MK19] and [CM17]. Unverified.
- **Sargano et al. 2024**, MediaPipe head pose against motion capture for sign language video: seen in a search result only ("good" yaw, worse pitch and roll). Unverified.
- **[EP07] miss rates per variant**: the three gaze variants' values at each size were read from chart labels whose order the text extraction did not preserve; given as ranges.
- **[PP18] refined selection times**: in a figure only, not read as numbers. The 1.44 s for button-switched eye-then-head is [BG20]'s own re-run.
- **[HM15]**: the eye trackers' accuracy and the gain values are not in the paper.
- **Degree conversions marked derived** assume the stated screen diagonal, aspect ratio and viewing distance ("about 60 cm", "approximately 2.5 feet", "13-inch").
- **Precision of webcam head pose while still, and translation accuracy in millimetres**: no published evaluation found. The camera scale used above (2.49 px/mm) rests on an assumed 70 deg field of view.
- **Whether macOS exposes hit target rectangles** for target-aware mechanisms: not researched.

## Sources

Head movement refining gaze:

- [LL14] Špakov, Isokoski, Majaranta. Look and Lean: Accurate Head-Assisted Eye Pointing. ETRA 2014, 35-42. [Author copy][LL14]. doi:10.1145/2578153.2578157
- [HM15] Kurauchi, Feng, Morimoto, Betke. HMAGIC: Head Movement and Gaze Input Cascaded Pointing. PETRA 2015, article 47. [Author copy][HM15]. doi:10.1145/2769493.2769550
- [PP18] Kytö, Ens, Piumsomboon, Lee, Billinghurst. Pinpointing: Precise Head- and Eye-Based Target Selection for Augmented Reality. CHI 2018, paper 81. [Copy read][PP18]. doi:10.1145/3173574.3173655
- [BG20] Sidenmark, Mardanbegi, Ramirez Gomez, Clarke, Gellersen. BimodalGaze: Seamlessly Refined Pointing with Gaze and Filtered Gestural Head Movement. ETRA 2020. [Accepted version][BG20]. doi:10.1145/3379155.3391312
- [HB23] Hou, Newn, Sidenmark, Khan, Bækgaard, Gellersen. Classifying Head Movements to Separate Head-Gaze and Head Gestures as Distinct Modes of Input. CHI 2023. [Accepted version][HB23]. doi:10.1145/3544548.3581201
- [JA15] Jalaliniya, Mardanbegi, Pederson. MAGIC Pointing for Eyewear Computers. ISWC 2015, 155-158. [Abstract][JA15]. doi:10.1145/2802083.2802094
- [MG99] Zhai, Morimoto, Ihde. Manual and Gaze Input Cascaded (MAGIC) Pointing. CHI 1999, 246-253. [doi:10.1145/302979.303053][MG99]. Not read. [Authors' slides][MG99-slides] read.
- [ST99] Stahl. Amplitude of human head movements associated with horizontal saccades. Experimental Brain Research 126, 1999, 41-54. [Abstract][ST99]. doi:10.1007/s002210050715

Magnification:

- [EP07] Kumar, Paepcke, Winograd. EyePoint: Practical Pointing and Selection Using Gaze and Keyboard. CHI 2007, 421-430. [Author copy][EP07]. doi:10.1145/1240624.1240692
- [BI04] Bates, Istance. Towards eye based virtual environment interaction for users with high-level motor disabilities. ICDVRAT 2004. [Proceedings copy][BI04].
- [BI02] Bates, Istance. Zooming interfaces! Enhancing the performance of eye controlled pointing devices. ASSETS 2002, 119-126. [doi:10.1145/638249.638272][BI02]. Not read.
- [AS05] Ashmore, Duchowski, Shoemaker. Efficient Eye Pointing with a Fisheye Lens. Graphics Interface 2005, 203-210. [Author copy][AS05]. doi:10.1145/1089508.1089542

Target-aware:

- [MI04] Miniotas, Špakov, MacKenzie. Eye Gaze Interaction with Expanding Targets. CHI 2004 Late Breaking Results, 1255-1258. [Author copy][MI04]. doi:10.1145/985921.986037
- [SM05] Špakov, Miniotas. Gaze-Based Selection of Standard-Size Menu Items. ICMI 2005, 124-128. [Author copy][SM05]. doi:10.1145/1088463.1088486
- [MI06] Miniotas, Špakov, Tugoy, MacKenzie. Speech-Augmented Eye Gaze Interaction with Small Closely Spaced Targets. ETRA 2006, 67-72. [Author copy][MI06].
- [AG15] Lutteroth, Penkar, Weber. Gaze vs. Mouse: A Fast and Accurate Gaze-Only Click Alternative. UIST 2015, 385-394. [Author copy][AG15]. doi:10.1145/2807442.2807461

Head-only pointing:

- [MA15] Magee, Felzer, MacKenzie. Camera Mouse + ClickerAID: Dwell vs. Single-Muscle Click Actuation in Mouse-Replacement Interfaces. HCII 2015, LNCS 9175, 74-84. [Author copy][MA15].
- [RM18] Roig-Maimó, MacKenzie, Manresa-Yee, Varona. Head-tracking interfaces on mobile devices: Evaluation using Fitts' law and a new multi-directional corner task for small displays. IJHCS 112, 2018, 1-15. [Author copy][RM18]. doi:10.1016/j.ijhcs.2017.12.003
- [CM17] Cuaresma, MacKenzie. FittsFace: Exploring Navigation and Selection Methods for Facial Tracking. HCII 2017, LNCS 10278, 403-416. [Author copy][CM17]. doi:10.1007/978-3-319-58703-5_30
- [MK19] Minakata, Hansen, MacKenzie, Bækgaard. Pointing by Gaze, Head, and Foot in a Head-Mounted Display. ETRA 2019, article 69. [Author copy][MK19]. doi:10.1145/3317956.3318150
- [QT17] Qian, Teather. The Eyes Don't Have It: An Empirical Comparison of Head-Based and Eye-Based Selection in Virtual Reality. SUI 2017, 91-98. [Author copy][QT17]. doi:10.1145/3131277.3132182
- [BE02] Betke, Gips, Fleming. The Camera Mouse: Visual Tracking of Body Features to Provide Computer Access for People With Severe Disabilities. IEEE TNSRE 10(1), 2002, 1-10. [Author copy][BE02]. doi:10.1109/TNSRE.2002.1021581
- [GI00] Gips, Betke, Fleming. The Camera Mouse: Preliminary Investigation of Automated Visual Tracking for Computer Access. RESNA 2000. [Author copy][GI00].

Head pose from a camera:

- [HA22] Hammadi, Grondin, Ferland, Lebel. Evaluation of Various State of the Art Head Pose Estimation Algorithms for Clinical Scenarios. Sensors 22(18), 2022, 6850. [Open access][HA22]. doi:10.3390/s22186850
- [KA19] Kartynnik, Ablavatski, Grishchenko, Grundmann. Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs. 2019. [arXiv:1907.06724][KA19]
- [HE22] Hempel, Abdelrahman, Al-Hamadi. 6D Rotation Representation for Unconstrained Head Pose Estimation. 2022. [arXiv:2202.12555][HE22]

Apple:

- [AP-hp] Mac User Guide, macOS Sequoia 15: [Move the pointer using head pointer on Mac][AP-hp].
- [AP-pc] Mac User Guide, macOS Sequoia 15: [Change Pointer Control settings for accessibility on Mac][AP-pc].

Earlier notes in this repository: physical-limits (camera scale), on branch `research/physical-limits`.

[LL14]: <https://homepages.tuni.fi/oleg.spakov/publications/Spakov_ETRA_14a.pdf>
[HM15]: <https://www.cs.bu.edu/fac/betke/papers/Kurauchi-etal-HMAGIC-PETRA-2015.pdf>
[PP18]: <https://3dvar.com/Kyt%C3%B62018Pinpointing.pdf>
[BG20]: <https://eprints.lancs.ac.uk/142666/1/Head_Gaze_pointing_ETRA20.pdf>
[HB23]: <https://eprints.lancs.ac.uk/id/eprint/189056/1/HeadBoost_Accepted.pdf>
[JA15]: <https://pure.itu.dk/en/publications/magic-pointing-for-eyewear-computers/>
[MG99]: <https://doi.org/10.1145/302979.303053>
[MG99-slides]: <https://www.cs.princeton.edu/courses/archive/fall08/cos436/Zhai/magic.pdf>
[ST99]: <https://europepmc.org/article/MED/10333006>
[EP07]: <https://hci.stanford.edu/publications/2007/chi253-kumar.pdf>
[BI04]: <https://oneswitch.org.uk/OS-REPOSITORY/MUSEUM/VARIOUS/VR/ICDArchive2021/2004/P/S09_N2_Bates_Istance_2004.pdf>
[BI02]: <https://doi.org/10.1145/638249.638272>
[AS05]: <http://andrewd.ces.clemson.edu/research/vislab/docs/gi05.pdf>
[MI04]: <https://www.yorku.ca/mack/chi04b.pdf>
[SM05]: <https://homepages.tuni.fi/oleg.spakov/publications/Spakov_ICMI_05.pdf>
[MI06]: <https://www.yorku.ca/mack/etra2006.html>
[AG15]: <https://www.cs.auckland.ac.nz/~lutteroth/publications/LutterothPenkarWeber-Actigaze2015.pdf>
[MA15]: <https://www.yorku.ca/mack/hcii2015b.html>
[RM18]: <https://www.yorku.ca/mack/ijhcs2018.html>
[CM17]: <https://www.yorku.ca/mack/hcii2017.html>
[MK19]: <https://www.yorku.ca/mack/etra2019a.html>
[QT17]: <https://www.csit.carleton.ca/~rteather/pdfs/sui17b.pdf>
[BE02]: <http://www.cs.bu.edu/fac/betke/papers/betke-gips-fleming-nsre02.pdf>
[GI00]: <https://www.cs.bu.edu/fac/betke/cs591/papers/gips-betke-fleming.pdf>
[HA22]: <https://pmc.ncbi.nlm.nih.gov/articles/PMC9502716>
[KA19]: <https://arxiv.org/abs/1907.06724>
[HE22]: <https://arxiv.org/abs/2202.12555>
[AP-hp]: <https://support.apple.com/guide/mac-help/mchlb2d4782b/15.0/mac/15.0>
[AP-pc]: <https://support.apple.com/guide/mac-help/unac899/15.0/mac/15.0>
