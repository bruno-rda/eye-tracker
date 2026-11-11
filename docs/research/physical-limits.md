# What do the eye and the camera physically allow?

Research for [#2](https://github.com/bruno-rda/eye-tracker/issues/2). Compiled 2026-11-10.

## Answer

- **Eye bound.** Fixation itself scatters by about 0.1 to 0.3 deg (radius of the area holding 68% to 95% of gaze samples, 5 s fixation on a dot, head fixed). No estimator can be more precise than that, and calibration cannot be more accurate than that.
- **Camera bound.** The iris centre moves about 0.20 mm per degree of horizontal eye rotation and 0.16 mm per degree vertical. At 1920 px across an assumed 70 deg horizontal field of view and 55 cm, that is about **0.5 px/deg horizontal, 0.4 px/deg vertical**. The iris is about 29 px wide.
- **Consequence.** The camera binds, not the eye. Resolving 1 deg needs the iris centre located to about 0.5 px relative to the head; reaching the eye's own floor (0.2 deg) would need about 0.1 px. One pixel of landmark error is about 2 deg, or 190 native display pixels.
- **Angle kappa** (about 5 deg, SD about 1.3 deg between people) is a fixed per-eye offset. It bounds calibration-free accuracy only.

The camera's video resolution and field of view are assumptions here (sibling ticket #5). Recompute with the formula in [Camera](#camera).

## Eye

### Foveal extent

| Quantity | Value | Source |
|---|---|---|
| Retinal scale | 288 um per degree of visual angle | Drasdo and Fowler 1974, in [Kolb, Webvision, Facts and Figures](https://www.webvision.pitt.edu/book/part-xiii-facts-and-figures-concerning-the-human-retina/) |
| Fovea, rim to rim | 1.5 mm (Polyak 1941); 1.2 to 1.5 mm (Ahnelt and Kolb, unpublished) | [Kolb, Webvision](https://www.webvision.pitt.edu/book/part-xiii-facts-and-figures-concerning-the-human-retina/) |
| Rod-free zone, horizontal diameter | 0.350 mm (1.25 deg), mean of 8 retinas, 7 donors aged 27 to 44 | [Curcio et al. 1990](https://doi.org/10.1002/cne.902920402) (abstract) |
| Foveola radius | about 30 arcmin | [Rucci and Poletti 2015](https://doi.org/10.1146/annurev-vision-082114-035742), citing Curcio et al. 1990 |
| Region of peak cone density | within 0.032 deg^2 | [Curcio et al. 1990](https://doi.org/10.1002/cne.902920402) (abstract) |

Derived: 1.5 mm / 0.288 mm/deg = 5.2 deg for the fovea rim to rim.

The high-acuity region is about 1 deg across. Fixation is finer than that: the measured scatter below is a few tenths of a degree, so the foveola's size is not the working limit.

### Fixational eye movements

The eye never holds still. Three components:

| Component | Size | Rate / speed | Source |
|---|---|---|---|
| Tremor | about 1 arcmin; other estimates 6 arcsec peak (Eizenman et al. 1985) and 17.5 arcsec median (Ratliff and Riggs 1950) | spectral peak 40 to 100 Hz | [Rucci and Poletti 2015](https://doi.org/10.1146/annurev-vision-082114-035742); [Ko, Snodderly and Poletti 2016](https://doi.org/10.1016/j.visres.2016.03.006) |
| Drift | classical: 1.5 to 4 arcmin displacement; "typically less than 0.13 degrees" | classical median 4 arcmin/s (trained observers, Ditchburn 1973); 52 arcmin/s mean instantaneous speed, range 30 to 89 across 14 observers fixating a dot | [Rucci and Poletti 2015](https://doi.org/10.1146/annurev-vision-082114-035742); [Otero-Millan et al. 2014](https://doi.org/10.3389/fnint.2014.00052); [Cherici et al. 2012](https://doi.org/10.1167/12.6.31) |
| Microsaccades | classical definition below 30 arcmin (some below 12); "tend to be less than 0.5 deg, but can go up to 1 deg or more"; measured mean 20 arcmin, SD 7, when fixating a dot | 1 to 3 per second; measured 1.32 per second, SD 0.5 | [Rucci and Poletti 2015](https://doi.org/10.1146/annurev-vision-082114-035742); [Otero-Millan et al. 2014](https://doi.org/10.3389/fnint.2014.00052); [Cherici et al. 2012](https://doi.org/10.1167/12.6.31) |

Tremor is far below anything a webcam resolves and is irrelevant here. Drift and microsaccades set the floor.

### Fixation scatter: the precision floor

[Cherici et al. 2012](https://doi.org/10.1167/12.6.31) ([PDF](https://aplab.bcs.rochester.edu/assets/download/PDFs/articles/ChericiEtAl12.pdf)): 14 observers (3 trained, 11 untrained), Dual Purkinje Image tracker at 1 kHz, bite bar, right eye only, 5 s trials, fixating a 4 arcmin dot at 125 cm.

| Area containing gaze | Area (arcmin^2) | Equivalent-circle radius |
|---|---|---|
| 68% of the time, mean over observers | 275 | 9.4 arcmin = 0.16 deg |
| 75%, mean (SD 251; range 71 to 994) | 367 | 10.8 arcmin = 0.18 deg |
| 75%, trained group / untrained group | 132 / 431 | 6.5 / 11.7 arcmin |
| 95%, mean | 967 | 17.5 arcmin = 0.29 deg (paper: "18 arcmin radius circle") |
| 68%, average of earlier studies of trained observers | 73, SD 50 | 4.8 arcmin = 0.08 deg |
| 75%, no fixation marker, mean | 1281 | 20.2 arcmin = 0.34 deg |

Radius is derived as sqrt(area / pi); the distributions are not circular or normal (same paper), so it is a summary only.

Implications:

- Precision floor: about 0.1 deg (trained) to 0.3 deg (95% radius, mostly untrained), head fixed, 5 s. Head-free desktop use is unverified and can only be worse or equal.
- Accuracy floor: calibration records where the eye pointed while the user looked at a target, so it inherits the same scatter. Unverified as a measured figure; it follows from the scatter above.
- A dwell on a visible target is steadier than a stare at blank screen (367 vs 1281 arcmin^2).

### Angle kappa

Clinical angle kappa is "the angle between the visual line and the pupillary axis" ([Choi and Kim 2013](https://doi.org/10.3341/kjo.2013.27.6.421)). The ticket's "optical axis vs visual axis" offset is strictly angle alpha; kappa is the measurable stand-in (unverified: no source read for the alpha definition).

| Population | Method | Angle kappa (mean, SD) | Source |
|---|---|---|---|
| Tehran, 800 eyes, age 14 to 81 | Orbscan II | 5.46 deg, 1.33; falls 0.015 deg/year with age; myopes 5.13, emmetropes 5.72, hyperopes 5.52 | [Hashemi et al. 2010](https://doi.org/10.3928/1081597x-20100114-06) (abstract) |
| Mashhad, 977 subjects, age 18 to 45 | Orbscan II | 4.97 deg, 1.38; right eyes 5.16, left eyes 4.78 | [Gharaee et al. 2015](https://doi.org/10.5812/ircmj.17873) |
| Seoul, mean age 59 | Orbscan II | men 4.70 deg, 2.70; women 4.89 deg, 2.14 | [Choi and Kim 2013](https://doi.org/10.3341/kjo.2013.27.6.421) |

Implications (inference from the figures above, not a measured result):

- Ignoring kappa biases a geometric gaze estimate by about 5 deg.
- Assuming a population mean leaves about 1.3 deg SD between people, plus left/right differences.
- Kappa is anatomical and nearly constant (0.015 deg/year), so a per-user calibration absorbs it. For one calibrated user it does not limit accuracy.

## Eyeball geometry

| Quantity | Value | Source |
|---|---|---|
| Eyeball diameter | 24.2 mm transverse, 23.7 mm sagittal, 22.0 to 24.8 mm axial; transverse range 21 to 27 mm (CT, 250 adults) | [Bekerman et al. 2014](https://doi.org/10.1155/2014/503645) |
| Visible iris diameter (white-to-white) | 11.71 mm, SD 0.42; normal range about 10.7 to 12.6 mm (Orbscan II, 743 eyes of 390 subjects) | [Rufer et al. 2005](https://doi.org/10.1097/01.ico.0000148312.01805.53) (abstract) |
| Centre of rotation, horizontal movements | 15.3 mm behind corneal apex, SD 1.5, range 12.4 to 18.0 (59 subjects, saccades of +-11.9 deg) | [Ohlendorf et al. 2022](https://doi.org/10.1111/opo.12940) |
| Centre of rotation, vertical movements | 12.5 mm behind corneal apex, SD 1.3 to 1.4, range 7.3 to 15.7 | [Ohlendorf et al. 2022](https://doi.org/10.1111/opo.12940) |
| Centre of rotation, earlier values | 13 to 15 mm; 13.5 mm (emmetropes); 14.9 mm horizontal and 12.3 mm vertical (Fry and Hill 1962, 6 subjects) | as cited in [Ohlendorf et al. 2022](https://doi.org/10.1111/opo.12940); [Fry and Hill 1962](https://doi.org/10.1097/00006324-196211000-00001) not read |
| Entrance pupil plane | 3.6 mm behind corneal apex | value used by [Ohlendorf et al. 2022](https://doi.org/10.1111/opo.12940) |

The quantity the calculation needs is the lever arm L: distance from the centre of rotation to the plane of the feature the camera tracks. Ohlendorf et al. measured exactly this with a camera (lateral displacement of the pupil centre per degree of rotation) and then added 3.6 mm to report it from the corneal apex. So:

- L horizontal = 15.3 - 3.6 = **11.7 mm** (SD 1.5)
- L vertical = 12.5 - 3.6 = **8.9 mm** (SD about 1.4)
- With the older 13.5 mm centre of rotation: L = 9.9 mm.

Caveat: iris landmark models report the iris (limbus) centre, not the pupil centre. For a spherical cornea of radius 7.6 mm (the radius Ohlendorf et al. assume) and an 11.71 mm chord, the limbus plane is 7.6 - sqrt(7.6^2 - 5.855^2) = 2.75 mm behind the apex, about 0.85 mm in front of the pupil plane, which would lengthen L by about 7%. Derived, unverified; ignored below.

## Camera

### Formula

```
dx_mm(theta)  = L * sin(theta)                 iris-centre displacement, eye rotation theta
f_px          = (W / 2) / tan(HFOV / 2)        focal length in pixels
s             = f_px / Z                        image scale at the eye, px per mm
k             = L * sin(1 deg) * s              px per degree, near straight-ahead
              = 0.01745 * L * W / (2 * Z * tan(HFOV / 2))
gaze error (deg) = landmark error (px) / k
```

L in mm, Z = camera-to-eye distance in mm, W = image width in px, HFOV = horizontal field of view of the delivered frame. Pinhole model, eye near the optical axis, small rotations. Off-axis rotation scales by cos(theta): 3% less at 15 deg.

### Assumptions

- W = 1920 (16:9, 1920x1080). Apple states "12MP Center Stage camera with support for Desk View" and "1080p HD video recording" for the MacBook Pro 14-inch (M4 Pro or M4 Max, 2024): [Apple tech specs](https://support.apple.com/en-us/121553).
- HFOV = 70 deg. **Unverified assumption.** Apple publishes no field of view for this camera. The delivered 1080p frame is presumably a crop of a wider 12 MP sensor (unverified). Apple's Studio Display spec lists a 12MP Ultra Wide Center Stage camera at 122 deg (unverified: seen in a search snippet, page not read).
- Z = 550 mm, range 500 to 600.

### Worked example

```
dx      = 11.7 mm * sin(1 deg) = 0.204 mm/deg horizontal
          8.9 mm * sin(1 deg)  = 0.155 mm/deg vertical
f_px    = 960 / tan(35 deg)    = 1371 px
s       = 1371 / 550           = 2.49 px/mm
k_h     = 0.204 * 2.49         = 0.51 px/deg
k_v     = 0.155 * 2.49         = 0.39 px/deg
iris    = 11.71 mm * 2.49      = 29 px wide
```

### Sensitivity (W = 1920)

Horizontal / vertical px per degree, and iris width in px:

| HFOV | f_px | Z = 500 mm | Z = 550 mm | Z = 600 mm |
|---|---|---|---|---|
| 50 deg | 2059 | 0.84 / 0.64, iris 48 | 0.76 / 0.58, iris 44 | 0.70 / 0.53, iris 40 |
| 60 deg | 1663 | 0.68 / 0.52, iris 39 | 0.62 / 0.47, iris 35 | 0.57 / 0.43, iris 33 |
| 70 deg | 1371 | 0.56 / 0.43, iris 32 | 0.51 / 0.39, iris 29 | 0.47 / 0.35, iris 27 |
| 80 deg | 1144 | 0.47 / 0.36, iris 27 | 0.42 / 0.32, iris 24 | 0.39 / 0.30, iris 22 |
| 90 deg | 960 | 0.39 / 0.30, iris 23 | 0.36 / 0.27, iris 20 | 0.33 / 0.25, iris 19 |
| 100 deg | 806 | 0.33 / 0.25, iris 19 | 0.30 / 0.23, iris 17 | 0.27 / 0.21, iris 16 |
| 122 deg | 532 | 0.22 / 0.17, iris 13 | 0.20 / 0.15, iris 11 | 0.18 / 0.14, iris 10 |

k scales linearly with W: a 3840 px wide frame over the same field of view doubles every figure.

Calibration check for ticket #8: the iris width in pixels gives s directly (s = iris px / 11.71 mm, within the 0.42 mm SD), without knowing the field of view.

### What 1 degree demands

At the worked example (70 deg, 55 cm):

- 1 deg of eye rotation = 0.51 px horizontal, 0.39 px vertical.
- 1 px of iris-centre error = 2.0 deg horizontal, 2.6 deg vertical.
- To match the eye's 0.2 deg floor: 0.10 px horizontal, 0.08 px vertical.

On the display ([Apple tech specs](https://support.apple.com/en-us/121553): 14.2 in, 3024x1964 at 254 ppi, so 302.4 x 196.4 mm, 10 px/mm):

- 1 deg at 55 cm = 9.6 mm = 96 native px (87 at 50 cm, 105 at 60 cm).
- The screen subtends 30.7 x 20.2 deg at 55 cm.
- The iris centre travels about **15.5 px** across the full screen width and **7.8 px** across its height.
- 1 px of landmark error moves the estimate about 190 native px (19 mm) horizontally.

### Notes for the prototype (#8) and targets (#9)

- The requirement is on the iris centre **relative to the head**. Head translation moves the iris in the image at the same px/mm, so 0.2 mm of uncompensated head motion looks like 1 deg of eye rotation. Head rotation error adds to gaze error degree for degree. Both follow from the geometry above; not measured.
- Vertical is harder: shorter lever arm (8.9 vs 11.7 mm), and eyelid occlusion of the iris (unverified here).
- Averaging two eyes and N frames lowers random error by up to sqrt(2N) only if errors are independent (unverified for landmark models); frame averaging costs latency.
- Not assessed: lens blur, sensor noise, motion blur, video compression and image-signal-processor sharpening. They can only lower effective precision below the pixel-geometry figure.
- Whether a landmark model reaches 0.1 to 0.5 px repeatability is an empirical question for #4 and #8.

## Unverified or not consulted

- Camera field of view and delivered resolution of this Mac's built-in camera (assumed 70 deg, 1920x1080). Owned by #5.
- Studio Display 122 deg figure: search snippet only.
- Fry and Hill 1962 and Curcio et al. 1990 full texts, Hashemi et al. 2010 and Rufer et al. 2005 full texts: abstracts or citing papers only.
- Kolb's figures are a textbook compilation; the originals (Polyak 1941, Drasdo and Fowler 1974) were not read.
- Angle alpha definition and the optical-axis framing: no source read.
- Limbus-plane depth (2.75 mm): derived from a spherical-cornea assumption.
- Head-free fixation scatter at a desk: no source found in this pass; the scatter figures are head-fixed.
- Accuracy floor after calibration and all "Implications" bullets: inferences from the cited figures, not measurements.
