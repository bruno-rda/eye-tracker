# Eye Tracker

Moving the cursor with the eyes, using only a laptop webcam.

## Language

**Point of gaze**:
The location on the screen the eyes are fixating.
_Avoid_: Gaze point, look position

**Accuracy**:
The offset between the estimated and the true point of gaze, in degrees of visual angle.
_Avoid_: Error, precision

**Precision**:
The spread of the estimated point of gaze while the eyes hold one fixation, in degrees of visual angle.
_Avoid_: Jitter, noise, stability

**Latency**:
The time from light reaching the camera to the cursor moving.
_Avoid_: Lag, delay

**Data loss**:
The share of frames with no estimated point of gaze, outside blinks, while the face is in view.
_Avoid_: Dropout, tracking loss

**Fixation target**:
A mark shown at a known screen position for the eyes to fixate, making the true point of gaze known.
_Avoid_: Target, stimulus, dot

**Hit target**:
An on-screen element the cursor must land on.
_Avoid_: Target, button

**Requirement**:
A number that defines success for accuracy, precision, latency, data loss or landing on hit targets.
_Avoid_: Target, goal, threshold
