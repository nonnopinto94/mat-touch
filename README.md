# mat-touch

A "virtual touchscreen" for projected surfaces. A webcam watches the projected area, finds hands and feet (MediaPipe), and sends them as multitouch events **only** to one Chromium tab, using the Chrome DevTools Protocol (CDP).

It works with any web page that accepts touch input. Its first client is an interactive koi pond projected on a child's play mattress.

> Status: in development. Milestones M1 (camera + calibration) and M2 (browser connection) are done. Hand/foot detection is not implemented yet. See [Roadmap](#roadmap).

## How it works

```
webcam ──> detection ──> calibration ──> tracking ──> CDP ──> browser tab
           (MediaPipe)   (homography)    (ids,        (Input.dispatchTouchEvent)
                                          smoothing)
```

1. **Calibration**: you click the 4 corners of the projected area in the webcam image. mat-touch computes a homography from camera coordinates to the projected area.
2. **Detection** *(M3, planned)*: MediaPipe Pose (or Hands) finds hands and feet in each frame.
3. **Tracking** *(M4, planned)*: points get stable ids, debouncing and One Euro smoothing.
4. **Output**: touches are injected into a single browser tab via CDP. For the page they are indistinguishable from a real touchscreen: it receives Touch Events and Pointer Events with `pointerType: "touch"`.

### Why CDP instead of a system-wide virtual touchscreen

Touches exist **only inside the chosen tab**. The desktop never receives anything, even if the browser crashes or closes. This matters when a child is the user. It also needs no special permissions (`/dev/uinput`) and no screen mapping: coordinates are the page's own.

The output sits behind an `OutputBackend` interface, so a system-wide backend (uinput) can be added later without touching the rest.

## Requirements

- Linux with an X11 session
- Python 3.10+ with Tkinter
- Chromium or Google Chrome
- A USB webcam. For the real setup it should be mounted next to the projector lens and point the same way, so touches land where the light hits the hand.

## Installation

```sh
sudo apt install python3-tk python3-venv
git clone <this repo> mat-touch
cd mat-touch
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### 1. Start Chromium with remote debugging

Always use a **dedicated profile** (`--user-data-dir`), never your personal browsing profile. The debugging port listens on `127.0.0.1` only.

Chromium from apt or Google Chrome:

```sh
chromium --user-data-dir="$HOME/.config/mat-touch/chromium" \
  --remote-debugging-port=9222 http://localhost:8417/?mode=mat
```

Chromium from **snap** (Ubuntu's default) cannot use hidden folders in your home. With a path under `~/.config` it silently falls back to your **personal profile**. Use this instead:

```sh
chromium --user-data-dir="$HOME/snap/chromium/common/mat-touch" \
  --remote-debugging-port=9222 http://localhost:8417/?mode=mat
```

For the projection setup, add `--kiosk --no-first-run --noerrdialogs --disable-pinch --overscroll-history-navigation=0`. With two screens, also add `--window-position=<x>,0` to place the window on the projector output.

### 2. Start mat-touch

```sh
python -m mat_touch
```

If a valid calibration is saved, mat-touch asks whether to reuse it and skips to step 2.

### The wizard

**Step 1: camera and calibration**
- Choose the webcam from the list. A live preview appears.
- Click the 4 corners of the projected area, in any order. mat-touch sorts them as TL, TR, BR, BL and shows the labels. Drag a point to correct it.
- **Ricomincia** clears the points. **Conferma** saves them and goes to step 2.

**Step 2: browser connection**
- Enter the CDP port (default `9222`) and press **Collega**.
- mat-touch lists the open tabs. If there is only one, it is preselected.
- If no browser answers, the window shows the exact command to start Chromium.
- **Avanti** connects to the chosen tab and enables touch emulation on it (`maxTouchPoints: 10`).

**Step 3: running**
- The preview shows the calibrated area.
- *Test without vision*: click and drag on the preview to touch the page at the matching point. This checks calibration and connection without detection. Leaving the area or releasing the mouse lifts the finger.
- **Ricalibra** goes back to step 1. **Cambia scheda** goes back to step 2, which you also use to reconnect if the browser restarts.

The UI is in Italian, since the end users are Italian.

### Configuration

Settings are saved in `~/.config/mat-touch/config.json`:

| Key | Meaning |
|---|---|
| `camera` | Webcam device, e.g. `/dev/video0` |
| `corners` | 4 corners `[x, y]` in normalized camera coordinates `[0,1]` (TL, TR, BR, BL). These are resolution-independent and in the same space as MediaPipe landmarks. |
| `cdp_port` | Chromium remote debugging port |
| `min_confidence`, `frames_in`, `frames_out`, `filter_min_cutoff`, `filter_beta` | Detection and tracking parameters (used from M3/M4) |

A missing or corrupt file falls back to defaults.

## Testing without a projector

Everything can be developed on a laptop:

1. Serve the test page: `python3 -m http.server 8418 -d tools`
2. Start Chromium (see above) on `http://127.0.0.1:8418/touch-test.html`. The page draws every touch it receives with its id, position and event type, plus a log of start and end events.
3. In step 1, "calibrate" by clicking the corners of a sheet of paper or of a screen seen by the webcam.
4. In step 3, click on the preview and watch the touches appear in the page.

Unit tests:

```sh
python -m tests.test_calibration
```

## CDP touch semantics

These were verified on Chromium:

- `touchStart` and `touchMove` take the **full** set of active points, and Chromium works out which ones changed. A new id in a `touchStart` starts only that finger.
- A point missing from a `touchMove` is **not** lifted.
- `touchEnd` lifts exactly the listed points. An empty list lifts all of them.
- `touchEnd` with no active touch is an error.

`CdpOutput.send()` hides this: you pass the full set of active touches, and it sends the right events.

## Project layout

```
mat_touch/
  __main__.py        entry point: python -m mat_touch
  app.py             Tkinter wizard (steps 1-3)
  camera.py          webcam listing and opening (V4L2)
  calibration.py     corner ordering, homography, saving
  config.py          ~/.config/mat-touch/config.json
  outputs/
    base.py          OutputBackend interface; touches are normalized [0,1] in the projected area
    cdp.py           Chrome DevTools Protocol backend
    dryrun.py        prints touches, for tests
tools/
  touch-test.html    test page that draws received touches
tests/               unit tests
models/              MediaPipe models, downloaded on first run (not committed)
scripts/             launch scripts (planned)
```

## Roadmap

- [x] **M1**: camera and calibration
- [x] **M2**: CDP connection, test page, click-on-preview touches
- [ ] **M3**: detection with MediaPipe Pose (then Hands), drawn on the preview
- [ ] **M4**: tracking, debouncing, One Euro filter, live multitouch, page hardening script, keyboard shortcuts, pause button
- [ ] **M6**: `scripts/start.sh`, automatic reconnection, webcam v4l2 settings

## License

MIT, see [LICENSE](LICENSE).
