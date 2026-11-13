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

**Estimator**:
The part that turns camera frames into a point of gaze.
_Avoid_: Tracker, model, predictor

**Method**:
The idea an estimator implements.
_Avoid_: Approach, algorithm, technique

**Recorded session**:
One sitting captured whole, every camera frame and on-screen event on one clock, so it can be replayed.
_Avoid_: Recording, dataset, run

**Replay**:
Feeding a recorded session to an estimator in recorded order, as the live camera would.
_Avoid_: Playback, offline run, simulation

**Block**:
A stretch of a recorded session with one purpose.
_Avoid_: Phase, segment, trial

**Calibration pool**:
The block whose fixation targets an estimator may be told the positions of.
_Avoid_: Calibration set, training set

**Test block**:
A block whose fixation targets score an estimator and are never shown to it.
_Avoid_: Validation set, test set

**Retained window**:
The frames of one fixation that are scored, the same for every estimator.
_Avoid_: Sample window, fixation window

**Development session**:
A recorded session estimators may be tuned on.
_Avoid_: Training session, train split

**Held-out session**:
A recorded session designated before recording to score estimators, never to tune them.
_Avoid_: Test session, validation set, test split

**Ceiling**:
An estimator's accuracy when calibrated on the fixation targets it is scored on.
_Avoid_: Oracle, upper bound
