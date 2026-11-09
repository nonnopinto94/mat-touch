# mat-touch

Turn any projected surface into a multitouch screen with a cheap webcam.

mat-touch watches a projected area, finds hands and feet with MediaPipe, and sends them as touches to **one browser tab** through the Chrome DevTools Protocol. The page gets real touch events, the same as from a touchscreen, so any touch-enabled web page works without changes.

It was built to let a toddler play with a koi pond ([hush-pond-webcam](https://github.com/nonnopinto94/hush-pond-webcam)) projected on their play mat.

- **Only the tab gets touched.** The desktop never sees an event, even if the browser crashes. That matters when a two-year-old is the user.
- **Multitouch.** Several children, hands and feet at once, each with a stable id.
- **Calibration in four clicks.** Click the corners of the projection in the webcam image. Oblique projectors and wide-angle cameras are fine.
- **Testable without a projector.** A test page shows every touch it receives, and you can click on the camera preview to send touches by hand.

## Requirements

- Linux with an X11 session
- Python 3.10+ with Tkinter (`python3-tk`)
- Chromium or Google Chrome
- A USB webcam. For the real setup, mount it right next to the projector lens, pointing the same way, so a raised hand is seen and lit along nearly the same line.

## Install

```bash
sudo apt install python3-tk python3-venv
git clone https://github.com/nonnopinto94/mat-touch.git
cd mat-touch
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

The first time you start detection, mat-touch downloads the MediaPipe model (~9 MB) into `models/`.

## Quick start

**1. Start the page you want to touch.** For example, the pond:

```bash
git clone https://github.com/nonnopinto94/hush-pond-webcam.git
cd hush-pond-webcam && python3 -m http.server 8417
```

**2. Start Chromium with remote debugging and a separate profile.** On Ubuntu Chromium is a snap, and a snap can't use hidden folders in your home. If you point `--user-data-dir` into `~/.config`, it ignores the path and opens your **personal profile** instead. So use:

```bash
chromium --user-data-dir="$HOME/snap/chromium/common/mat-touch" \
  --remote-debugging-port=9222 "http://localhost:8417/?mode=mat"
```

With Chromium from apt, or with Google Chrome, `--user-data-dir="$HOME/.config/mat-touch/chromium"` works too.

On the projector, add `--kiosk --no-first-run --noerrdialogs --disable-pinch --overscroll-history-navigation=0`. With two screens, add `--window-position=<x>,0`, where `<x>` is where the projector output starts.

**3. Start mat-touch:**

```bash
.venv/bin/python -m mat_touch
```

## Using it

The wizard has three steps. It remembers everything, and next time it offers to reuse the saved calibration.

1. **Calibrate.** Pick the webcam, then click the four corners of the projected image, in any order. Drag a corner to fix it.
2. **Connect.** Press *Collega* (connect). mat-touch lists the open tabs on port 9222. Pick one and press *Avanti* (next). If no browser answers, it shows the command to start one.
3. **Play.** The preview shows what mat-touch sees:
   - green dots are detected hands and feet inside the area;
   - red circles are touches sent to the page.

   The big button pauses touches. Clicking on the preview sends a touch by hand.

The interface is in Italian.

### Tuning

Step 3 has a few sliders, applied live:

| Slider | What it does |
| --- | --- |
| Confidenza minima | Ignore detections below this confidence |
| Fotogrammi per entrare | Frames a hand must be seen before it touches. Higher means fewer false touches but more delay. |
| per uscire | Frames a hand may go missing before its finger lifts. Higher means touches survive brief dropouts. |
| Smoothing | Filter cutoff in Hz. Lower is steadier but laggier. |

You can also choose the detector:

- *Pose*, the default, uses the whole body. It works best with the camera at an angle.
- *Mani* (hands) is for a camera close to the mat.

### Keyboard shortcuts

These work in the browser tab, including in kiosk mode:

| Keys | Action |
| --- | --- |
| `Ctrl+Alt+P` | Pause / resume touches |
| `Ctrl+Alt+Q` | Quit mat-touch |

mat-touch also blocks the context menu, text selection and dragging in the page, so a long press doesn't open anything.

### Configuration

Settings live in `~/.config/mat-touch/config.json` and are written by the wizard. A few have no slider:

| Key | Default | Meaning |
| --- | --- | --- |
| `feet` | `true` | With Pose, feet touch too |
| `margin` | `0.05` | How far outside the area a point still counts, as a fraction of the area size |
| `filter_beta` | `1.0` | How quickly smoothing lets go on fast moves |

### Troubleshooting

- **Slow detection.** On a laptop i5-8250U, Pose runs at about 5 fps and Hands at about 7. Cheap webcams also slow down in dim light because of auto exposure. Lock exposure with `v4l2-ctl --list-ctrls`, then `v4l2-ctl -c <control>=<value>`.
- **"Nessun browser sulla porta 9222".** Chromium isn't running with `--remote-debugging-port`, or another Chromium using the same profile was already open. Close it and start again.
- **Touches land in the wrong place.** Recalibrate (*Ricalibra*) after moving the camera or the projector. Turn off projector keystone if you can: calibration handles the distortion.

## Development

### How it works

```
webcam ─> detection ─> homography ─> tracking ─> CDP ─> browser tab
          MediaPipe    camera to      ids, debounce,     Input.dispatchTouchEvent
                       projection     One Euro
```

Everything after the camera runs in one background thread (`pipeline.py`), so the UI never blocks and touches have a single sender. Output goes through an `OutputBackend` interface. CDP is the only backend today; a system-wide uinput backend could be added without touching the rest.

### Layout

```
mat_touch/
  app.py             Tkinter wizard
  pipeline.py        capture → detection → mapping → tracking → output
  camera.py          webcam listing (V4L2)
  calibration.py     corner ordering, homography
  tracker.py         stable ids, debouncing
  filters.py         One Euro filter
  config.py          settings file
  detectors/         MediaPipe Pose and Hands, model download
  outputs/           OutputBackend, CDP, dry run
tools/touch-test.html  page that draws every touch it receives
tests/
```

### Tests

```bash
.venv/bin/python -m tests.test_calibration
.venv/bin/python -m tests.test_tracker
```

For an end-to-end check without a projector:

1. Serve the test page with `python3 -m http.server 8418 -d tools`.
2. Open `http://127.0.0.1:8418/touch-test.html` in Chromium, started as in the quick start.
3. In step 1, calibrate on a sheet of paper the webcam can see.
4. In step 3, click on the preview and watch the touches appear on the page.

### CDP touch semantics

I checked these on Chromium, because the docs don't spell them out:

- `touchStart` and `touchMove` take the full set of active points, and Chromium works out what changed.
- A point missing from a `touchMove` is **not** lifted.
- `touchEnd` lifts exactly the points it lists. An empty list lifts all of them.
- `touchEnd` with no active touch is an error.

`CdpOutput.send()` takes care of this. You always pass the full set of active touches.

## License

[MIT](LICENSE)
