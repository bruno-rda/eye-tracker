# Measuring gaze accuracy without a reference tracker

Research for #7. Sources are peer-reviewed papers and the eye-tracking reporting guidelines. Papers that describe a tracker are cited for measurement practice only, not for estimation method.

Labels used below:

- **unverified**: no primary source read for the claim.
- **second-hand**: the claim is taken from a review that cites the original; the original was not read.
- **derived**: arithmetic or reasoning done here on top of sourced inputs; not a published result.

## Answer

1. Ground truth is a fixation target at a known screen position. The procedure is called validation: show targets, keep the samples from the period when the eye rests on each target, compare with the target position ([Holmqvist 2023][h23]).
2. Accuracy is the distance between the target and the centre of the retained estimates, per fixation. Precision is the spread of the retained estimates, as RMS sample-to-sample (RMS-S2S) and as standard deviation (STD). Both in degrees, with data loss reported next to them ([Holmqvist 2023][h23], [Niehorster 2020][n20], [Dunn 2024][d24]).
3. Fixation is assured by design, not detected: a small high-contrast target, an attention task or a key press by the participant, and a fixed discard of 0.5 to 0.8 s after target onset. At 30 Hz the usual saccade detectors do not transfer, so samples are time-locked to the target ([Saxena 2024][s24]).
4. Test targets must differ from calibration targets and cover the whole screen, otherwise accuracy looks better than it is ([Holmqvist 2023][h23]). Accuracy also decays with time since calibration, so it is measured early and late ([Ehinger 2019][e19]).
5. For this project the number of test fixations matters more than the number of frames per fixation. One second of retained frames (30) per fixation is enough; resolving 0.3 degrees between two estimators needs on the order of 90 test fixations per session (derived, section 9).

## 1. Target design

Shape and size:

- Of seven common target shapes, fixated for 17 s per trial, only a bullseye combined with a cross hair gave both low dispersion and low microsaccade rate ([Thaler 2013][t13], abstract; full text not read).
- With a circular target, microsaccade rate fell and microsaccade magnitude rose linearly as the target grew ([McCamy 2013][m13], abstract). Small targets keep fixational movements small.
- Whether the target that minimises dispersion also gives better accuracy is unknown ([Holmqvist 2023][h23]).
- Sizes in use: bullseye with cross hair, 0.6 degree diameter ([Saxena 2024][s24]); bullseye 0.5 degree outer, 0.25 degree inner for moving targets ([Ehinger 2019][e19]).

Keeping attention on the target:

- Accuracy is higher when the participant signals that they are looking at the target than when the operator or the software decides ([Nyström 2013][ny13], abstract; [Holmqvist 2023][h23]).
- Self-paced: participants pressed space once they felt their eyes had stopped moving; the fixation at the key press was analysed ([Ehinger 2019][e19]).
- Go/no-go: the target turned into a check mark or a cross and only one required a key press ([Feit 2017][f17]).
- Discrimination: a letter flashed for 0.05 s at the target near the end of a 2 s display, and the wrong answer repeated the target ([Krafka 2016][k16]).
- A pulsating target was used to direct fixation to its centre ([Krafka 2016][k16], [Valliappan 2020][v20]).

Static versus moving targets:

- Pursuit calibration: a target moving along the screen border; samples are kept only while eye and target motion correlate, which detects attention. With constant speed, durations of 10 s or more (11.6 degrees/s or slower) gave accuracy under 1 degree; 5 s (23.3 degrees/s) was 2.15 times worse. Correlation was lost at corners, where catch-up movements occur. 15 participants, Tobii X300 at 60 Hz ([Pfeuffer 2013][p13]).
- A 30 to 60 s pursuit calibration along a horizontal path was not significantly worse than dots appearing in random order ([Blignaut 2017][b17], abstract).
- With a webcam, offset during pursuit was about the same as during fixation: 211 px versus 172 px in the lab ([Semmelmann 2018][sw18], abstract).
- In both pursuit calibration studies the test still used static points. No source read here validates a moving target as ground truth for accuracy at webcam frame rates: unverified.

## 2. Knowing the participant was fixating

- After a saccade to a target, participants may undershoot or overshoot, correct, and only then fixate. A selection method for the fixation period is required; there is no single standard ([Holmqvist 2023][h23]).
- Saccade latency after target onset: mean 210 ms, median 167 ms, measured with a phone camera at 30 Hz ([Valliappan 2020][v20]).
- Fixed discards in the literature: recording started 0.5 s after the target moved ([Krafka 2016][k16]); first 0.8 s and last 0.2 s of each 2 s test target discarded, the end to remove anticipation ([Pfeuffer 2013][p13]).
- Retained windows: 1 s (60 frames at 60 Hz), taken while gaze stayed within a radius of the target, or offline the 1 s window closest to the target ([Feit 2017][f17]); 200 ms out of 1500 ms, chosen to be unlikely to contain microsaccades ([Niehorster 2020][n20]); the whole 2500 ms display, reduced with the median ([Saxena 2024][s24]).
- At 30 Hz, velocity and dispersion based event detection is not established. Samples were time-locked to target presentation instead ([Saxena 2024][s24]).
- Blinks and loss: a fixation was dropped when more than 2/3 of its samples had no tracked eye; 2.4% of fixations were dropped ([Feit 2017][f17]). Blinks account for about 2% of samples (second-hand, [Holmqvist 2023][h23]).
- Selecting the window by closeness to the target, as in the offline variant above, uses the estimate itself and so favours the estimator. Derived: when estimators are compared, the window must come from the target timeline alone.
- A camera-based estimator returns a value during blinks unless told otherwise. Derived: blink frames must be flagged once, independent of any estimator, and excluded identically for all.

## 3. Definitions and formulas

For one fixation with retained samples (x_i, y_i), i = 1..n, in degrees, and target (x_t, y_t):

- **Accuracy**: mean difference between the reported gaze locations near a validation target and the target position ([Holmqvist 2023][h23]). Operationalised as the offset between the target and the mean of the samples ([Feit 2017][f17], per axis), or their median ([Saxena 2024][s24]), or as the angle between target and fixation location ([Ehinger 2019][e19]).

  `accuracy = sqrt((mean(x) - x_t)^2 + (mean(y) - y_t)^2)`

- **Precision, RMS-S2S** ([Niehorster 2020][n20], [Holmqvist 2023][h23]):

  `RMS-S2S = sqrt( (1/(n-1)) * sum_{i=1..n-1} ((x_{i+1} - x_i)^2 + (y_{i+1} - y_i)^2) )`

- **Precision, STD** ([Niehorster 2020][n20], [Holmqvist 2023][h23]):

  `STD = sqrt( (1/n) * sum_{i=1..n} ((x_i - mean(x))^2 + (y_i - mean(y))^2) ) = sqrt(STD_x^2 + STD_y^2)`

- **BCEA** ([Niehorster 2020][n20]): `BCEA = 2 * k * pi * s_x * s_y * sqrt(1 - rho^2)`, `k = -ln(1 - P)`; k = 1 gives P = 0.632. Unit degrees squared.
- **Data loss**: proportion of samples without an estimate, or discarded in analysis ([Holmqvist 2023][h23], [Dunn 2024][d24]).

What the two precision measures see ([Niehorster 2020][n20]):

- RMS-S2S reflects sample-to-sample velocity. It is insensitive to slow spread, and it changes with sampling frequency, so it is not comparable across frame rates (second-hand for the frequency effect).
- STD reflects spatial spread and grows with window length for smooth signals. There is no correct window length; it has to be fixed and stated.
- RMS-S2S / STD is sqrt(2) for white signals and lower for smooth signals. In simulation RMS-S2S was stable beyond about 30 samples.
- Derived: a smoothing estimator lowers RMS-S2S without improving STD. Comparing estimators therefore needs both, on the same window, and STD is the fairer of the two.

Derived: averaging per-sample distances to the target instead of taking the distance of the mean mixes precision into accuracy. With zero true offset the expected value is 0.89 x STD (Rayleigh mean), not 0. Use the centre first, then the distance.

## 4. Pixels and degrees

- Conversion needs viewing distance, screen size and resolution. The small-angle approximation (one multiplication factor) is acceptable when the screen is under 20 degrees wide ([Holmqvist 2023][h23]).
- Angle between two screen points p and q, seen from an eye at E (geometry, derived): `theta = acos( (p - E) . (q - E) / (|p - E| * |q - E|) )`. For an eye on the screen normal through the centre at distance d, a point at offset s from the centre lies at `atan(s / d)`.
- This display: 14.2 inch, 3024 x 1964 px at 254 px per inch ([Apple][apple]), so 0.1 mm per px and 302 x 196 mm. Derived from that:

| Distance | 1 degree at centre | Screen width | Screen height | px per degree at left or right edge (radial) |
| --- | --- | --- | --- | --- |
| 50 cm | 87 px | 33.6 degrees | 22.2 degrees | 95 |
| 55 cm | 96 px | 30.8 degrees | 20.2 degrees | 103 |
| 60 cm | 105 px | 28.2 degrees | 18.6 degrees | 111 |

- Derived consequences: the screen is wider than 20 degrees, so the single-factor conversion is off by up to 9% at the edge. A 50 to 60 cm distance range changes the factor by 20%, more than any difference between estimators that the protocol should resolve. Distance must be known per fixation, or results also reported in a distance-free unit.
- Distance-free units in use: cm ([Feit 2017][f17], [Krafka 2016][k16], [Valliappan 2020][v20]); px and percent of screen size ([Semmelmann 2018][sw18]).

## 5. Reporting

- Aggregate bottom-up: per fixation, then over targets, then over blocks, then over participants ([Ehinger 2019][e19], [Saxena 2024][s24], [Feit 2017][f17]).
- Robust centre: 20% winsorized mean with inter-quartile range ([Ehinger 2019][e19]). Winsorizing shapes the data in favour of accuracy ([Saxena 2024][s24]).
- Percentiles: 25th, 50th, 75th and 90th. Offset at the 90th percentile was more than six times the 25th (0.93 versus 0.15 cm horizontally), and the standard deviation across fixations was about as large as the mean (0.47 cm, SD 0.64 cm). 80 participants, two commercial trackers ([Feit 2017][f17]). A single mean hides this.
- Per axis: accuracy was 0.1 cm worse vertically ([Feit 2017][f17]).
- Per screen region: corners can be worse by a factor of 3 in precision and by 1 to 10 degrees in accuracy, depending on the system ([Holmqvist 2023][h23]). Precision was worse in the bottom row and right-most column ([Feit 2017][f17]). A webcam system reported 1.3 degrees centrally against 1.4 degrees overall ([Kaduk 2024][kd24]).
- Over time: accuracy measured directly after calibration is a best case. A 13-target subset was repeated after about 4.7 and 6.3 minutes; one device decayed by about 30% ([Ehinger 2019][e19]).
- For interaction: a gaze target that captures 95% of samples has side `S = 2 * (O + 2 * sigma)`, with O the offset and sigma the standard deviation along that axis ([Feit 2017][f17]). This turns accuracy and precision into a minimum button size.
- Reference values for webcams: accuracy 2.4 degrees and precision 0.47 degrees, best of several models on 30 fps video, 65 participants ([Saxena 2024][s24]); 1.4 degrees and 1.1 degrees for a commercial system, where precision was the SD across participants because no target was fixated twice ([Kaduk 2024][kd24]); 3.94 degrees in the lab ([Semmelmann 2018][sw18]).

## 6. Keeping calibration and test data apart

Within a session:

- Accuracy is underestimated when the same points serve calibration and validation, or when validation covers only part of the stimulus area ([Holmqvist 2023][h23]).
- Choosing a number of calibration points also chooses the mapping fitted to them, and different mappings give different accuracy on the same data ([Holmqvist 2023][h23]). Nine points beat two by about 0.2 degrees on one commercial tracker (second-hand, [Holmqvist 2023][h23]).
- Pursuit used for calibration, 16 static points used for test ([Pfeuffer 2013][p13]).
- Calibration simulated from frames at 13 fixed locations, test on the remaining locations; with few calibration points the result got slightly worse, attributed to overfitting ([Krafka 2016][k16]).
- Test set fixed in advance as the last 500 samples per person; k calibration samples drawn at random from the rest, repeated 10 times, mean and standard deviation reported per k ([Park 2019][pk19]).
- About 100 calibration frames (under 30 s) took a phone model from 1.92 to 0.46 cm; a hold-out calibration set was used to screen recordings ([Valliappan 2020][v20]).
- Calibration blocks placed before and after the task blocks ([Saxena 2024][s24]).
- Derived: consecutive frames of one fixation are near duplicates. A frame-level random split leaks; the split must be by fixation or by block.

Across sessions:

- Without recalibration, accuracy of one consumer tracker degraded by 0.30 degrees plus 0.13 degrees per month; drift of 0.2 degrees in 15 minutes on a tower-mounted tracker (both second-hand, [Holmqvist 2023][h23]).
- A second validation at the end of a recording is recommended to detect change ([Holmqvist 2023][h23]).
- No source read here evaluates a webcam estimator calibrated in one session and tested in another: unverified.

## 7. Target counts and durations in the literature

| Study | Purpose | Targets | Time per target | Retained |
| --- | --- | --- | --- | --- |
| Survey of published studies ([Holmqvist 2023][h23]) | calibration | 9 most common (67% of those reporting), then 5, 13, 3 | not given | not given |
| [Ehinger 2019][e19] | calibration | 13 | operator paced | not given |
| [Ehinger 2019][e19] | test | 49 (7 x 7, plus or minus 18.2 by 7.7 degrees), then 13 twice | self paced | fixation at key press |
| [Saxena 2024][s24] | test, webcam | 13 x 10 trials | 2500 ms | all, median |
| [Feit 2017][f17] | test | 30 | about 2 s | 1 s |
| [Pfeuffer 2013][p13] | test | 16 | 2 s | 1.0 s |
| [Niehorster 2020][n20] | precision | 213 | 1500 ms | 200 ms |
| [Krafka 2016][k16] | training and calibration | 13 fixed plus random | about 2 s | from 0.5 s |
| [Valliappan 2020][v20] | calibration | random dots, or 60 s zig-zag pursuit | not given | about 100 frames suffice |

Only 41% of surveyed studies reported the number of calibration targets, 3.4% a self-measured accuracy, 4.4% precision and 3.8% data loss ([Holmqvist 2023][h23]).

## 8. Reporting guidelines

Minimal reporting guideline, 2023 edition ([Dunn 2024][d24]; consensus of a 47-member group over 3 years; read through a summarising fetch, wording not checked verbatim):

- A1 manufacturer and model, A2 software and firmware versions, A3 technology, A4 sampling frequency, A5 head movement restrictions, A6 eyes recorded, A7 parameters recorded, A8 environment lighting, A9 calibration, A10 measurement uncertainty, A11 data processing steps, A12 data loss, B1 signal latencies, C1 participant to display distance with display dimensions.
- A9 asks for the calibration method, the number of targets with their colour, size, shape, duration and position or movement, any participant task, the acceptance criterion, and the validation procedure described to the same standard.
- A10 asks for the uncertainty of every reported quantity; for precision it names RMS-S2S, standard deviation and BCEA.

Empirical foundations paper ([Holmqvist 2023][h23], table 7 and table 6):

- Report empirically determined accuracy, precision and data loss for the analysed signal, and the software that computed them.
- Determine sampling frequency empirically from the recorded signal.
- Report whether validation points are the same as calibration points, who controlled target acceptance (participant, operator, software), drift checks and recalibrations, exclusion criteria, and all processing parameters.
- For work that develops or evaluates tracking methods: full description of hardware, software, settings, environment and participant characteristics.

## 9. Constraints on a recorded session

Inputs from sibling tickets, relayed by the coordinator and not re-verified here: camera at 30 fps with a host-clock timestamp per frame; a steady fixation scatters 0.1 to 0.3 degrees with the head fixed; published calibrated webcam accuracy is 2 to 3 degrees.

Everything in this section is derived.

What must be recorded:

1. Every frame with its timestamp, and the target position on the same clock, so the retained window is defined by the target timeline and is identical for all estimators.
2. Target appearance, size, position, onset and offset; the participant task and any key press with its timestamp.
3. Display size and resolution, and eye-to-screen distance per fixation or at least per block.
4. A blink and face-lost flag per frame from one fixed procedure, applied to all estimators.
5. Session metadata: lighting, time since the start, glasses, seating.

Structure:

1. Separate calibration and test blocks. The test block is frozen: no estimator, parameter or filter may be tuned on it.
2. Test target positions differ from calibration positions and cover the full screen including edges and corners.
3. The calibration block is a pool. Estimators that need k points take subsets of it, so accuracy can be reported against k with random subsets repeated.
4. A short test block directly after calibration and another at the end of the session, to separate best-case accuracy from accuracy after a few minutes.
5. Split by fixation or block, never by frame.
6. Whole sessions on other days held out, for calibrate-once and calibration-free estimators.
7. If a pursuit segment is recorded, it goes to the calibration pool. Accuracy is scored on static targets only.

Per fixation:

1. Target shown for 2 to 2.5 s. Discard the first 0.5 to 0.8 s, and the last 0.2 s if the next position is predictable.
2. Retain at least 1 s, which is 30 frames, the length beyond which RMS-S2S was stable. Use the same window length for every fixation and estimator, because STD depends on it.
3. A task or key press that can only be done while looking at the target.
4. Drop a fixation when most retained frames are flagged; report the share dropped.

How many test fixations:

- The centre of 30 frames has a standard error of STD / sqrt(30) if frames are independent: 0.09 to 0.18 degrees for a precision of 0.5 to 1 degree. Smoothing makes frames dependent and the gain smaller.
- The eye's own scatter of 0.1 to 0.3 degrees is a per-fixation offset of the ground truth. More frames do not average it out; more fixations do.
- Offset varies between fixations by about as much as its mean (section 5), so about 1 degree or more at webcam accuracy. This term dominates, and it shrinks only with the number of fixations N.
- Estimators are compared on the same fixations, so the relevant spread is that of the paired difference in offset, sd_d. The eye's scatter is common to both and largely cancels. Smallest N to detect a mean difference D with 80% power at a two-sided 5% level: `N = (2.8 * sd_d / D)^2`.

| sd_d | D = 0.5 degrees | D = 0.3 degrees | D = 0.2 degrees |
| --- | --- | --- | --- |
| 1.0 degree | 32 | 88 | 196 |
| 0.5 degree | 8 | 22 | 49 |

- sd_d is unknown until a pilot session is replayed through two estimators: unverified. Planning value: about 90 test fixations per session, 4 minutes at 2.5 s each, which is above the 13 to 49 targets usual in the literature. A calibration pool of 13 to 25 points adds about 1 minute.
- Region-level statements need the same N per region. With 9 regions and 90 fixations there are 10 per region, enough only for differences near 1 degree. Finer maps need pooling over sessions.
- With one participant, N counts fixations, and conclusions hold for this user and setup only.

What to report per estimator and session: accuracy as median with 25th, 75th and 90th percentiles and mean, per axis and per screen region; precision as STD and RMS-S2S over the fixed window; data loss; the number of calibration points used; time since calibration; viewing distance; all of it in degrees and in cm or px.

## Not verified

- [Thaler 2013][t13], [Nyström 2013][ny13], [McCamy 2013][m13], [Blignaut 2017][b17], [Semmelmann 2018][sw18]: abstract only.
- [Dunn 2024][d24]: read through a summarising fetch; item names and the A9 and A10 content are as returned, not checked word for word.
- Holmqvist, Nyström and Mulvey 2012, "Eye tracker data quality: what it is and how to measure it" (ETRA), and the textbook conversion in Holmqvist and Andersson 2017: not read.
- Second-hand figures in sections 2, 3 and 6 (blink share, sampling-frequency effect on RMS-S2S, 9 versus 2 points, drift rates).
- A moving target as ground truth for accuracy; cross-session accuracy of webcam estimators; eye lag behind a pursuit target.
- All of section 9, in particular sd_d and the fixation counts that follow from it.

## Sources

- [Holmqvist et al. 2023, Eye tracking: empirical foundations for a minimal reporting guideline, Behavior Research Methods 55][h23]
- [Dunn et al. 2024, Minimal reporting guideline for research involving eye tracking (2023 edition), Behavior Research Methods 56][d24]
- [Niehorster et al. 2020, Characterizing gaze position signals and synthesizing noise during fixations in eye-tracking data, Behavior Research Methods 52][n20]
- [Ehinger et al. 2019, A new comprehensive eye-tracking test battery, PeerJ 7:e7086][e19]
- [Feit et al. 2017, Toward everyday gaze input: accuracy and precision of eye tracking and implications for design, CHI 2017][f17] ([author copy][f17pdf])
- [Pfeuffer et al. 2013, Pursuit calibration, UIST 2013][p13]
- [Saxena, Fink and Lange 2024, Deep learning models for webcam eye tracking in online experiments, Behavior Research Methods 56][s24]
- [Kaduk et al. 2024, Webcam eye tracking close to laboratory standards, Behavior Research Methods 56][kd24]
- [Semmelmann and Weigelt 2018, Online webcam-based eye tracking in cognitive science: a first look, Behavior Research Methods 50][sw18]
- [Krafka et al. 2016, Eye tracking for everyone, CVPR 2016][k16]
- [Park et al. 2019, Few-shot adaptive gaze estimation, ICCV 2019][pk19]
- [Valliappan et al. 2020, Accelerating eye movement research via accurate and affordable smartphone eye tracking, Nature Communications 11][v20]
- [Thaler et al. 2013, What is the best fixation target?, Vision Research 76][t13]
- [McCamy et al. 2013, The effects of fixation target size and luminance on microsaccades and square-wave jerks, PeerJ 1:e9][m13]
- [Nyström et al. 2013, The influence of calibration method and eye physiology on eyetracking data quality, Behavior Research Methods 45][ny13]
- [Blignaut 2017, Using smooth pursuit calibration for difficult-to-calibrate participants, Journal of Eye Movement Research 10(4)][b17]
- [Apple, MacBook Pro (14-inch, 2021) technical specifications][apple]

[h23]: https://doi.org/10.3758/s13428-021-01762-8
[d24]: https://doi.org/10.3758/s13428-023-02187-1
[n20]: https://doi.org/10.3758/s13428-020-01400-9
[e19]: https://doi.org/10.7717/peerj.7086
[f17]: https://doi.org/10.1145/3025453.3025599
[f17pdf]: https://www.microsoft.com/en-us/research/wp-content/uploads/2017/01/everyday_eyetracking-1.pdf
[p13]: https://doi.org/10.1145/2501988.2501998
[s24]: https://doi.org/10.3758/s13428-023-02190-6
[kd24]: https://doi.org/10.3758/s13428-023-02237-8
[sw18]: https://doi.org/10.3758/s13428-017-0913-7
[k16]: https://openaccess.thecvf.com/content_cvpr_2016/papers/Krafka_Eye_Tracking_for_CVPR_2016_paper.pdf
[pk19]: https://openaccess.thecvf.com/content_ICCV_2019/papers/Park_Few-Shot_Adaptive_Gaze_Estimation_ICCV_2019_paper.pdf
[v20]: https://doi.org/10.1038/s41467-020-18360-5
[t13]: https://doi.org/10.1016/j.visres.2012.10.012
[m13]: https://doi.org/10.7717/peerj.9
[ny13]: https://doi.org/10.3758/s13428-012-0247-4
[b17]: https://doi.org/10.16910/jemr.10.4.1
[apple]: https://support.apple.com/en-us/111902
