# Cursor control on macOS from Python

Research for #6. Sources read 2026-11-10. Target: Mac16,8, macOS 15.6, built-in display only.

Labels used below:

- **doc**: stated by a cited Apple or project source.
- **queried**: read on the target machine with a read-only call (no event posted, cursor not moved, no permission requested). Script in [Appendix](#appendix-read-only-queries).
- **unverified**: not settled by any source read and not tested. Repeated in [What must be measured](#what-must-be-measured).

"SDK header" means the Apple header shipped in `/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk/System/Library/Frameworks/CoreGraphics.framework/Headers/`.

## Answer

- Three APIs move the cursor: `CGWarpMouseCursorPosition`, `CGDisplayMoveCursorToPoint`, and posting a `kCGEventMouseMoved` Quartz event with `CGEventPost`.
- The two Core Graphics cursor functions generate no event (doc). A posted Quartz event enters the event stream and passes through event taps (doc).
- Posting events needs the Accessibility or PostEvent TCC privilege (doc). Apple documents no permission for the two cursor functions; whether they work without one is unverified.
- All three take points in the global display space, origin at the upper-left of the main display (doc). On this machine that space is 1512 x 982 points over 3024 x 1964 pixels, scale 2 (queried).
- Apple documents a 0.25 s default suppression interval for local hardware events after a posted Quartz event, with a default filter that suppresses nothing (doc). GLFW and SDL report that a warp freezes the cursor briefly unless `CGAssociateMouseAndMouseCursorPosition(true)` follows it (doc, third party). Not tested on macOS 15: unverified.
- Apple documents no duration for any of the three calls. The display refreshes at up to 120 Hz (doc), mode queried at 120 Hz.
- From Python: `ctypes` (stdlib, no dependency, loads Core Graphics on this machine: queried) or PyObjC `pyobjc-framework-Quartz` (three wheels, about 7.3 MB download). `pynput` and `PyAutoGUI` wrap PyObjC and use the event route; PyAutoGUI sleeps 10 ms per move plus 100 ms per call by default.
- A click is a mouse-down event followed by a mouse-up event, posted with `CGEventPost`. It needs the same privilege as any posted event.

## The three APIs

| | `CGWarpMouseCursorPosition(point)` | `CGDisplayMoveCursorToPoint(display, point)` | `CGEventPost(tap, mouseMovedEvent)` |
|---|---|---|---|
| Declared in | `CGRemoteOperation.h` | `CGDirectDisplay.h` | `CGEvent.h` |
| Available since | macOS 10.0, not deprecated [warp] | macOS 10.0, not deprecated [dmove] | macOS 10.4, not deprecated [post] |
| Coordinates | global display space [warp] | local to `display`, origin upper-left of that display; points outside the desktop are clipped [dmove] | global display space [mkmouse] |
| Applications see a mouse-moved event | no: "without generating or posting an event" [warp] | no: "doesn't generate events as a result of this move" [dmove] | yes: event is posted "immediately before any event taps instantiated for that location, and the event passes through any such taps" [post] |
| Visible cursor moves | yes [warp] | yes [dmove] | Apple's reference does not say. pynput and PyAutoGUI rely on it [pynput-src] [pag-osx]. Unverified on this machine. |
| Permission | none documented. Unverified. | none documented. Unverified. | Accessibility or PostEvent, see [Permissions](#permissions) |
| Suppression of hardware input afterward | none documented. Third-party reports of a freeze, see [Coexistence](#coexistence-with-the-trackpad) | none documented. GLFW applies the same workaround after this call [glfw] | documented: interval 0.25 s by default, filter permits all by default [src-h] |
| Return value | `CGError` [warp] | `CGError` [dmove] | none (`void`) [cgevent-h] |

Notes:

- With one display whose bounds origin is (0, 0) (queried), the local space of `CGDisplayMoveCursorToPoint` and the global space coincide, so the two cursor functions take the same numbers here.
- The 2013 Quartz Display Services guide says of the cursor functions: "To use these functions, your application must be in the foreground" [qds-cursor]. The current reference pages for the two move functions do not repeat this. Whether a terminal-launched Python process, which is not the foreground application, can warp the cursor is unverified.
- `CGAssociateMouseAndMouseCursorPosition(false)` disconnects the mouse from the cursor "while an application is in the foreground"; events then carry deltas with a constant absolute location [assoc]. Not wanted here: it removes hand control.
- `CGPostMouseEvent` is deprecated since 10.6 ("Use `CGEventCreateMouseEvent` instead") [remote-h]. Not a candidate.
- Consequence of "no event" for the two cursor functions: applications are not told the cursor moved. SDL compensates by synthesising its own motion event after a warp ("CGWarpMouseCursorPosition doesn't generate a window event") [sdl]. Whether hover states and cursor shape in other applications update after a warp without a later physical move is unverified.

### Posting a move event

```c
CGEventRef e = CGEventCreateMouseEvent(source, kCGEventMouseMoved, point, kCGMouseButtonLeft);
CGEventPost(kCGHIDEventTap, e);
CFRelease(e);
```

- `source` may be NULL [mkmouse]. `mouseButton` is ignored unless the type is one of the `kCGEventOtherMouse*` types [mkmouse].
- Tap locations: `kCGHIDEventTap` is "the point where HID system events enter the window server"; `kCGSessionEventTap` is "the point where HID system and remote control events enter a login session" [tap-hid] [tap-session]. pynput and PyAutoGUI post at `kCGHIDEventTap` [pynput-src] [pag-osx].
- pynput posts `kCGEventLeftMouseDragged` instead of `kCGEventMouseMoved` while it holds a button down [pynput-src]. Relevant if the user holds the trackpad button while gaze moves the cursor. Behaviour when the two disagree is unverified.

## Coexistence with the trackpad

What Apple documents:

- Event source, suppression interval: "the period of time in seconds that local hardware events may be suppressed after posting a Quartz event created with the specified event source. The default suppression interval is 0.25 seconds" [src-h].
- Event source, filter: "By default, the system does not suppress local hardware events from the keyboard or mouse during a short interval after a Quartz event is posted [...] and during a synthetic mouse drag" [src-h] [filter].
- Both are settable per source: `CGEventSourceSetLocalEventsSuppressionInterval`, `CGEventSourceSetLocalEventsFilterDuringSuppressionState` [src-h].
- Two suppression states exist: `kCGEventSuppressionStateSuppressionInterval` and `kCGEventSuppressionStateRemoteMouseDrag` [remote-h]. The header describes "remote mouse drag suppressing hardware mouse move events" after a posted left mouse down and defines a 60 s dead-switch timeout after which a warning is logged [remote-h].
- The global setter `CGSetLocalEventsSuppressionInterval` is deprecated since 10.6 and "not recommended for general use because of undocumented special cases and undesirable side effects"; valid range 0.0 to 10.0 s, default 0.25 s [setsupp]. Its symbol is still exported by the macOS 15.5 SDK stub (queried).
- `CGEventSourceGetLocalEventsSuppressionInterval(NULL)` returned 0.25 s on this machine (queried). The header says a NULL source returns the default constant [src-h].

What Apple does not document: any suppression after `CGWarpMouseCursorPosition` or `CGDisplayMoveCursorToPoint`.

What third parties report for the warp path (doc for their code, unverified for macOS 15 on this machine):

- GLFW 3.4, after warp or `CGDisplayMoveCursorToPoint`: "Calling this right after setting the cursor position prevents macOS from freezing the cursor for a fraction of a second afterwards", followed by `CGAssociateMouseAndMouseCursorPosition(true)` [glfw].
- SDL 3.2.0: "CGWarpMouse causes a short delay by default, which is preventable by calling this directly after. CGSetLocalEventsSuppressionInterval can also prevent it", followed by `CGAssociateMouseAndMouseCursorPosition(YES)` [sdl].
- Neither states the length of the freeze. That it equals the 0.25 s default interval is an inference from SDL's remark: unverified.

Why this decides the design: a gaze loop calls the move API at camera rate. If each call freezes hardware mouse movement for a fraction of a second, the trackpad cannot nudge the cursor while gaze control runs. The warp path then depends on the `CGAssociateMouseAndMouseCursorPosition(true)` workaround; the event path depends on the documented default filter, or on a private event source with the interval set to 0.

Detecting hand input, to yield to the trackpad:

- `CGEventSourceSecondsSinceLastEventType(stateID, eventType)` returns the elapsed time since the last event of a type for a source state [src-h].
- `kCGEventSourceStateHIDSystemState` "reflects the combined state of all hardware event sources posting from the HID system"; `kCGEventSourceStateCombinedSessionState` reflects "all event sources posting to the current user login session" [src-h].
- Whether events this process posts at `kCGHIDEventTap` count toward the HID system state, and whether the call needs a permission, are unverified. If synthetic events are excluded, this is a permission-light way to detect a physical nudge.
- An event tap can separate own events from hardware ones through the `kCGEventSourceUnixProcessID` and `kCGEventSourceUserData` fields [types-h], but listening is a separate privilege: ListenEvent "Allows the application to use CoreGraphics and HID APIs to listen to (receive) CGEvents and HID events from all processes" [pppc].

## Permissions

Posting events:

- Apple engineer, June 2018, on macOS 10.14: "We are changing the default system permissions for using CGEventTaps and CGEvent posting to remove this capability without explicit user permission." The first post attempt should raise an alert, and the grant lives under Privacy, Accessibility [forum-103992]. In the same thread the reporter saw no error from the failed post: "I'm not getting any errors, it just doesn't work" [forum-103992]. `CGEventPost` returns `void` [cgevent-h], so a denied post cannot be detected from its result.
- Two TCC privileges cover this, Accessibility and PostEvent. "In System Settings these both appear under Privacy & Security > Accessibility but they are different privileges" (Apple DTS engineer, April 2023). The same post: "Presumably Accessibility subsumes PostEvent, but I've never tested that" [forum-727984]. Unverified.
- PostEvent is defined as the policy "for the application to use CoreGraphics APIs to send CGEvents to the system event stream" [pppc].
- API: `CGPreflightPostEventAccess()` "Checks whether the current process already has event synthesizing access"; `CGRequestPostEventAccess()` "Requests event synthesizing access if absent, potentially prompting". Both macOS 10.15+ [cgevent-h]. Their reference pages carry no description [preflight].
- User flow: an alert appears, then the user enables the app under System Settings, Privacy & Security, Accessibility; an app not listed can be added with the add button [ax-help].

Which program gets the grant for a terminal-launched Python:

- "When a process makes a request, TCC tries to find the responsible code, that is, the nearest 'parent' of the process that the user knows about. [...] The algorithm that TCC uses to determine the responsible code is complex and evolves over time" (Apple DTS engineer, June 2024) [forum-751802].
- No Apple source read states that the terminal application is the responsible code for a Python child process. Expected outcome, unverified: the grant is requested for and stored against the terminal application (Terminal, iTerm2, the editor hosting the shell), so it must be re-granted per terminal application and not per script.
- `CGPreflightPostEventAccess()` returned `False` on this machine for `/usr/bin/python3` 3.9.6 run under this research agent's shell (queried). That says nothing about the user's own terminal.

Cursor functions:

- No Apple page or header read attaches a permission to `CGWarpMouseCursorPosition` or `CGDisplayMoveCursorToPoint`. Unverified whether they succeed with no grant. The returned `CGError` is the place to look [warp] [dmove].

Reading display geometry needed no grant (queried).

## Coordinates on the built-in display

Space and origin:

- Global display coordinate space: "relative to the upper-left corner of the main display" [bounds]. `CGEventGetLocation` returns global display coordinates; `CGEventGetUnflippedLocation` returns the location "relative to the lower-left corner of the main display" [cgevent-h]. So y grows downward for all three move APIs.
- AppKit's `NSEvent.mouseLocation` reports "screen coordinates" [mouseloc]; the page does not state the origin. pynput flips y with `CGDisplayPixelsHigh(0) - pos.y` when reading the position back [pynput-src], which implies a lower-left origin there.

Units:

- "Values that are integers in standard resolution, such as mouse coordinates, are floating-point values on a high-resolution display" [hires-explained]. `CGPoint` fields are doubles.
- `CGDisplayModeGetWidth` and `CGDisplayModeGetHeight` "return points (not pixels) as of OS X v10.8" [hires-apis]; `CGDisplayModeGetPixelWidth` and `CGDisplayModeGetPixelHeight` return pixels [dd-h].

This machine (queried, current display setting):

| Query | Result |
|---|---|
| `CGDisplayBounds(CGMainDisplayID())` | origin (0, 0), size 1512 x 982 |
| Current mode, points | 1512 x 982 |
| Current mode, pixels | 3024 x 1964 |
| Current mode, refresh rate | 120 Hz |
| `CGDisplayPixelsWide`, `CGDisplayPixelsHigh` | 1512, 982 |
| `CGDisplayScreenSize` | 301.2 x 195.6 mm |

- The panel is 3024 x 1964 pixels at 254 pixels per inch [specs]. At the current setting one point is 2 x 2 pixels, and valid cursor coordinates span x in [0, 1512), y in [0, 982).
- `CGDisplayPixelsWide` and `CGDisplayPixelsHigh` are documented as returning pixels [dd-h] but returned the point size here (queried). Do not use them for the pixel size; use the mode's pixel width and height.
- Pixel-level placement would need half-point coordinates. Whether the cursor honours fractional points is unverified.

Scaled resolutions (queried: HiDPI modes the built-in display offers, all scale 2):

| Points | Backing pixels |
|---|---|
| 960 x 600 | 1920 x 1200 |
| 1024 x 640 | 2048 x 1280 |
| 1024 x 665 | 2048 x 1330 |
| 1147 x 716 | 2294 x 1432 |
| 1147 x 745 | 2294 x 1490 |
| 1280 x 800 | 2560 x 1600 |
| 1352 x 845 | 2704 x 1690 |
| 1352 x 878 | 2704 x 1756 |
| 1512 x 945 | 3024 x 1890 |
| 1512 x 982 | 3024 x 1964 (current, native) |
| 1800 x 1125 | 3600 x 2250 |
| 1800 x 1169 | 3600 x 2338 |

- The cursor space follows the point size of the selected mode, not the panel. Changing the resolution in System Settings changes the coordinate range. Read `CGDisplayBounds` at start and map gaze to it; do not hard-code 1512 x 982.
- For modes whose backing size differs from 3024 x 1964, backing pixels are not panel pixels. Mapping camera-derived gaze to physical millimetres should go through `CGDisplayScreenSize` and the bounds in points.
- `backingScaleFactor` "does not represent anything concrete, such as pixel density or physical size, because it can vary based on the configured display mode" [hires-apis].

Camera housing:

- "On some Macs, the insets reflect the portion of the screen covered by the camera housing" (`NSScreen.safeAreaInsets`, macOS 12+) [safearea]. `NSScreen.frame` "includes any space currently occupied by the menu bar and dock" [frame]. The 982-point height therefore includes the strip beside the housing. Cursor behaviour when moved under the housing is unverified.

## How long a move takes

- No Apple page or header read gives a duration, a latency bound, or a statement of synchrony for `CGWarpMouseCursorPosition`, `CGDisplayMoveCursorToPoint` or `CGEventPost`. Unverified in every respect.
- Display: "ProMotion technology for adaptive refresh rates up to 120Hz"; fixed rates 47.95, 48.00, 50.00, 59.94, 60.00 Hz [specs]. Current mode 120 Hz (queried). At 120 Hz a refresh period is 8.33 ms; at 60 Hz, 16.67 ms. How the adaptive rate treats a cursor-only change is unverified.
- The only documented timing instrument in this API family: `CGGetEventTapList` reports `minUsecLatency`, `avgUsecLatency`, `maxUsecLatency` per installed tap, in microseconds [types-h] [cgevent-h]. It measures tap latency, not time to pixels.
- Third-party code inserts waits, which indicates the event path is asynchronous but gives no number for the OS: PyAutoGUI sleeps `DARWIN_CATCH_UP_TIME = 0.01` s after each move, "needed to allow OS time to catch up" [pag-osx] [pag-init].

## Reaching the APIs from Python

| Route | What it is | Cost |
|---|---|---|
| `ctypes` | stdlib FFI to `/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics` | No dependency. Signatures and the `CGPoint` struct (two doubles) must be declared by hand; a wrong declaration corrupts arguments silently. Constants (`kCGEventMouseMoved` and the like) must be copied from the headers. Works on this machine with `/usr/bin/python3` 3.9.6 for read-only calls (queried). |
| PyObjC `pyobjc-framework-Quartz` | Generated bindings, `import Quartz` | MIT. Version 13.0 (2026-10-30) requires Python >= 3.11 and pulls `pyobjc-core` and `pyobjc-framework-Cocoa` [pypi-quartz]. cp314 universal2 wheels: 6.73 MB + 0.39 MB + 0.22 MB download [pypi-core] [pypi-cocoa] [pypi-quartz]. Binary wheels, no compiler needed [pyobjc-install]. |
| `pynput` | Controller and listener classes over PyObjC | LGPLv3. 1.8.2 requires `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices`, `six` [pypi-pynput]. Sets position with `CGEventPost(kCGHIDEventTap, CGEventCreateMouseEvent(None, type, pos, button))` [pynput-src] (v1.8.1 source read). No warp path. |
| `PyAutoGUI` | Cross-platform automation over PyObjC | BSD. 0.9.54, last release 2023-05-24, sdist only [pypi-pag]. Each `moveTo` posts one event then sleeps 0.01 s [pag-osx], then sleeps `PAUSE = 0.1` s unless `PAUSE` is changed or `_pause=False` is passed; a fail-safe check runs before each call [pag-init]. Default settings alone exceed the 100 ms budget. No warp path. |

PyObjC details:

- `import Quartz` imports AppKit and nine sub-packages (CoreGraphics, ImageIO, ImageKit, CoreVideo, QuartzCore, PDFKit, QuartzFilters, QuickLookUI, QuartzComposer) [pyobjc-quartz-init]. `import Quartz.CoreGraphics` executes that package `__init__` first [py-import]. Import time is unverified.
- The PyObjC metadata lists every function this document names, including `CGWarpMouseCursorPosition`, `CGDisplayMoveCursorToPoint`, `CGAssociateMouseAndMouseCursorPosition`, `CGPreflightPostEventAccess` and the deprecated `CGSetLocalEventsSuppressionInterval` [pyobjc-meta]. Not called through PyObjC here: unverified at run time.
- PyAutoGUI passes the point as a Python tuple `(x, y)` [pag-osx]. `kCGDirectMainDisplay` is not wrapped: "Use `CGMainDisplayID()` instead" [pyobjc-notes].

`ctypes` details:

- "The Python global interpreter lock is released before calling any function exported by these libraries, and reacquired afterwards" (`CDLL`) [ctypes]. A slow call would not block other Python threads.
- Per-call overhead of either route is unverified.

Either route calls the same C functions; the choice does not change permissions or cursor behaviour. The dependency question is 7.3 MB of wheels and an import cost against hand-written signatures.

## Posting a click

```c
CGEventRef down = CGEventCreateMouseEvent(src, kCGEventLeftMouseDown, p, kCGMouseButtonLeft);
CGEventRef up   = CGEventCreateMouseEvent(src, kCGEventLeftMouseUp,   p, kCGMouseButtonLeft);
CGEventPost(kCGHIDEventTap, down);
CGEventPost(kCGHIDEventTap, up);
```

- Event types `kCGEventLeftMouseDown`, `kCGEventLeftMouseUp`, `kCGEventRightMouseDown`, `kCGEventRightMouseUp`; buttons `kCGMouseButtonLeft = 0`, `kCGMouseButtonRight = 1`, `kCGMouseButtonCenter = 2` [types-h]. Other buttons use `kCGEventOtherMouseDown` and `kCGEventOtherMouseUp` [mkmouse].
- The event carries its own position `p` in global display coordinates [mkmouse], so a click can be posted at a point without a prior move.
- Double click: set the integer field `kCGMouseEventClickState` to 2 on the second down and up; "A click state of 1 represents a single click. A click state of 2 represents a double-click" [types-h]. pynput does this [pynput-src].
- Same call sequence in PyAutoGUI and pynput [pag-osx] [pynput-src].
- Needs Accessibility or PostEvent, as any posted event. There is no click equivalent of the warp functions.
- Between a posted left mouse down and its up, the `kCGEventSuppressionStateRemoteMouseDrag` state applies; the default filter does not suppress hardware events in it [remote-h] [src-h]. A down without a matching up leaves a synthetic drag in progress.
- Timing between down and up that applications accept as a click is unverified.

Consequence for the architecture: a move-only build may avoid the permission entirely if the warp functions prove permission-free (unverified); the optional click module cannot.

## What must be measured

Nothing below is settled by documentation. All of it needs the target machine, the user's own terminal, and macOS 15.

1. Permission for the cursor functions: `CGError` and visible result of `CGWarpMouseCursorPosition` and `CGDisplayMoveCursorToPoint` from a terminal-launched Python with no Accessibility grant.
2. Foreground requirement: whether those calls work while another application is frontmost.
3. Post path without permission: whether `CGEventPost` is dropped silently, and whether the first attempt raises the alert.
4. Which entry appears in Privacy & Security, Accessibility (terminal application, Python binary, or other), and whether the grant survives a Python upgrade or a different terminal.
5. Whether an Accessibility grant alone enables posting, or PostEvent is requested separately.
6. Whether a posted `kCGEventMouseMoved` moves the visible cursor, at `kCGHIDEventTap` and at `kCGSessionEventTap`.
7. Freeze after a warp: length of any interval in which trackpad movement is ignored after `CGWarpMouseCursorPosition` and after `CGDisplayMoveCursorToPoint`, with and without `CGAssociateMouseAndMouseCursorPosition(true)` afterward. Repeat at the intended update rate (30 and 60 calls per second).
8. Freeze after a posted event: same test with a NULL source, and with a private source whose suppression interval is 0.
9. Trackpad clicks and drags during continuous programmatic moves: whether a physical click lands, whether a physical drag survives moves posted as `kCGEventMouseMoved`.
10. What other applications observe after a warp: hover highlights, cursor shape, tooltips, with no physical movement afterward.
11. Latency: time from the Python call to return, and from the call to the cursor changing on the panel (high-speed capture or a photodiode), for each of the three APIs. Distribution, not a single value. Compare with the 100 ms camera-to-cursor budget.
12. Call overhead: `ctypes` versus PyObjC per call, and `import Quartz` time on the chosen Python.
13. Fractional points: whether x.5 coordinates place the cursor on the intermediate pixel.
14. Edges: clamping at 0 and at 1512 x 982, hot corners, Dock and menu bar reveal, the strip beside the camera housing.
15. Hand-input detection: whether `CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateHIDSystemState, kCGEventMouseMoved)` ignores this process's own warps and posted events, and whether it needs a grant.
16. Coordinates after a resolution change in System Settings while the process runs.

## Could not be read

- Apple forum thread 789896 (PostEvent prompting, `CGRequestPostEventAccess`): the page returned a verification placeholder on two attempts. Nothing in this document relies on it.

## Appendix: read-only queries

Run with `/usr/bin/python3 -I` (3.9.6), stdlib only, on 2026-11-10. Calls made: `CGMainDisplayID`, `CGDisplayBounds`, `CGDisplayPixelsWide`, `CGDisplayPixelsHigh`, `CGDisplayCopyDisplayMode`, `CGDisplayCopyAllDisplayModes` (with `kCGDisplayShowDuplicateLowResolutionModes`), `CGDisplayModeGetWidth`, `CGDisplayModeGetHeight`, `CGDisplayModeGetPixelWidth`, `CGDisplayModeGetPixelHeight`, `CGDisplayModeGetRefreshRate`, `CGDisplayScreenSize`, `CGPreflightPostEventAccess`, `CGPreflightListenEventAccess`, `CGEventSourceGetLocalEventsSuppressionInterval(NULL)`.

Minimal form:

```python
import ctypes
cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")

class CGPoint(ctypes.Structure): _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]
class CGSize(ctypes.Structure): _fields_ = [("w", ctypes.c_double), ("h", ctypes.c_double)]
class CGRect(ctypes.Structure): _fields_ = [("o", CGPoint), ("s", CGSize)]

cg.CGMainDisplayID.restype = ctypes.c_uint32
cg.CGDisplayBounds.restype = CGRect
cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
b = cg.CGDisplayBounds(cg.CGMainDisplayID())
print(b.o.x, b.o.y, b.s.w, b.s.h)  # 0.0 0.0 1512.0 982.0

cg.CGPreflightPostEventAccess.restype = ctypes.c_bool
print(cg.CGPreflightPostEventAccess())  # False in the agent's shell
```

Symbol export (queried): `_CGWarpMouseCursorPosition`, `_CGDisplayMoveCursorToPoint`, `_CGAssociateMouseAndMouseCursorPosition`, `_CGEventPost`, `_CGEventSourceSetLocalEventsSuppressionInterval`, `_CGSetLocalEventsSuppressionInterval`, `_CGPreflightPostEventAccess`, `_CGRequestPostEventAccess` are all listed in `CoreGraphics.tbd` of the macOS 15.5 SDK.

## Sources

Bracketed tags in the text are links. Header tags ([remote-h], [cgevent-h], [src-h], [types-h], [dd-h]) quote the SDK header named in the tag (`CGRemoteOperation.h`, `CGEvent.h`, `CGEventSource.h`, `CGEventTypes.h`, `CGDirectDisplay.h`); headers have no public URL, so those links go to the matching Apple reference page.

- Apple reference: [warp], [dmove], [assoc], [post], [mkmouse], [filter], [setsupp], [preflight], [tap-hid], [tap-session], [bounds], [safearea], [frame], [mouseloc], [pppc].
- Apple guides and support: [qds-cursor] (archive, 2013), [hires-explained] and [hires-apis] (archive), [ax-help], [specs].
- Apple Developer Forums, Apple staff posts: [forum-103992] (Frameworks Engineer, June 2018), [forum-727984] (DTS Engineer, April 2023), [forum-751802] (DTS Engineer, June 2024).
- Python: [ctypes], [py-import].
- PyObjC: [pyobjc-install], [pyobjc-notes], [pyobjc-quartz-init], [pyobjc-meta], [pypi-quartz], [pypi-core], [pypi-cocoa].
- Third-party source, evidence of their own behaviour only: [pynput-src] (v1.8.1), [pypi-pynput], [pag-osx], [pag-init], [pypi-pag], [glfw] (3.4), [sdl] (3.2.0).

[warp]: <https://developer.apple.com/documentation/coregraphics/cgwarpmousecursorposition(_:)>
[dmove]: <https://developer.apple.com/documentation/coregraphics/cgdisplaymovecursortopoint(_:_:)>
[assoc]: <https://developer.apple.com/documentation/coregraphics/cgassociatemouseandmousecursorposition(_:)>
[post]: <https://developer.apple.com/documentation/coregraphics/cgevent/post(tap:)>
[mkmouse]: <https://developer.apple.com/documentation/coregraphics/cgevent/init(mouseeventsource:mousetype:mousecursorposition:mousebutton:)>
[filter]: <https://developer.apple.com/documentation/coregraphics/cgeventsource/setlocaleventsfilterduringsuppressionstate(_:state:)>
[setsupp]: <https://developer.apple.com/documentation/coregraphics/cgsetlocaleventssuppressioninterval(_:)>
[preflight]: <https://developer.apple.com/documentation/coregraphics/cgpreflightposteventaccess()>
[tap-hid]: <https://developer.apple.com/documentation/coregraphics/cgeventtaplocation/cghideventtap>
[tap-session]: <https://developer.apple.com/documentation/coregraphics/cgeventtaplocation/cgsessioneventtap>
[bounds]: <https://developer.apple.com/documentation/coregraphics/cgdisplaybounds(_:)>
[safearea]: <https://developer.apple.com/documentation/appkit/nsscreen/safeareainsets>
[frame]: <https://developer.apple.com/documentation/appkit/nsscreen/frame>
[mouseloc]: <https://developer.apple.com/documentation/appkit/nsevent/mouselocation>
[pppc]: <https://developer.apple.com/documentation/devicemanagement/privacypreferencespolicycontrol/services-data.dictionary>
[remote-h]: <https://developer.apple.com/documentation/coregraphics/quartz-event-services>
[cgevent-h]: <https://developer.apple.com/documentation/coregraphics/cgevent>
[src-h]: <https://developer.apple.com/documentation/coregraphics/cgeventsource>
[types-h]: <https://developer.apple.com/documentation/coregraphics/cgeventfield>
[dd-h]: <https://developer.apple.com/documentation/coregraphics/quartz-display-services>
[qds-cursor]: <https://developer.apple.com/library/archive/documentation/GraphicsImaging/Conceptual/QuartzDisplayServicesConceptual/Articles/MouseCursor.html>
[hires-explained]: <https://developer.apple.com/library/archive/documentation/GraphicsAnimation/Conceptual/HighResolutionOSX/Explained/Explained.html>
[hires-apis]: <https://developer.apple.com/library/archive/documentation/GraphicsAnimation/Conceptual/HighResolutionOSX/APIs/APIs.html>
[ax-help]: <https://support.apple.com/guide/mac-help/allow-accessibility-apps-to-access-your-mac-mh43185/mac>
[specs]: <https://support.apple.com/en-us/121553>
[forum-103992]: <https://developer.apple.com/forums/thread/103992>
[forum-727984]: <https://developer.apple.com/forums/thread/727984>
[forum-751802]: <https://developer.apple.com/forums/thread/751802>
[ctypes]: <https://docs.python.org/3/library/ctypes.html#ctypes.CDLL>
[pyobjc-install]: <https://pyobjc.readthedocs.io/en/latest/install.html>
[pyobjc-notes]: <https://pyobjc.readthedocs.io/en/latest/apinotes/Quartz.html>
[pyobjc-quartz-init]: <https://github.com/ronaldoussoren/pyobjc/blob/902694ce2c3409f166a8377b024fd9c1947097f0/pyobjc-framework-Quartz/Lib/Quartz/__init__.py>
[pypi-quartz]: <https://pypi.org/project/pyobjc-framework-Quartz/13.0/>
[pypi-core]: <https://pypi.org/project/pyobjc-core/13.0/>
[pypi-cocoa]: <https://pypi.org/project/pyobjc-framework-Cocoa/13.0/>
[pypi-pynput]: <https://pypi.org/project/pynput/1.8.2/>
[pypi-pag]: <https://pypi.org/project/PyAutoGUI/0.9.54/>
[pynput-src]: <https://github.com/moses-palmer/pynput/blob/v1.8.1/lib/pynput/mouse/_darwin.py>
[pag-osx]: <https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/_pyautogui_osx.py>
[pag-init]: <https://github.com/asweigart/pyautogui/blob/b4255d0be42c377154c7d92337d7f8515fc63234/pyautogui/__init__.py>
[glfw]: <https://github.com/glfw/glfw/blob/3.4/src/cocoa_window.m#L1603-L1638>
[sdl]: <https://github.com/libsdl-org/SDL/blob/release-3.2.0/src/video/cocoa/SDL_cocoamouse.m#L276-L296>
[pyobjc-meta]: <https://github.com/ronaldoussoren/pyobjc/blob/902694ce2c3409f166a8377b024fd9c1947097f0/pyobjc-framework-Quartz/Lib/Quartz/CoreGraphics/_metadata.py>
[py-import]: <https://docs.python.org/3/reference/import.html#regular-packages>
