"""Tkinter wizard.

Step 1: pick the webcam and click the 4 corners of the projected area.
Step 2: connect to a browser tab via Chrome DevTools Protocol.
Step 3: running: detected hands/feet become touches; clicking the preview sends a test touch.
"""
import queue
import shutil
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from . import calibration, camera, config
from .pipeline import MOUSE_ID, Pipeline
from .outputs import cdp

PREVIEW_W = 960   # max preview width in screen pixels
GRAB_R = 12       # click radius (screen px) to grab an existing point
FRAME_MS = 30
DETECTORS = {"Pose (corpo)": "pose", "Mani": "hands"}
LABELS = ["TL", "TR", "BR", "BL"]
# Snap Chromium cannot write hidden dirs in $HOME: it silently falls back to the personal profile.
_SNAP = (shutil.which("chromium") or "").startswith("/snap/")
PROFILE_DIR = "$HOME/snap/chromium/common/mat-touch" if _SNAP else "$HOME/.config/mat-touch/chromium"
CHROMIUM_CMD = f'chromium --user-data-dir="{PROFILE_DIR}" --remote-debugging-port={{port}} <url>'


def valid_corners(c) -> bool:
    return (isinstance(c, list) and len(c) == 4
            and all(isinstance(p, list) and len(p) == 2 for p in c))


class Preview(tk.Canvas):
    """Camera frame scaled to fit PREVIEW_W. Points are exchanged in normalized camera coords."""

    def __init__(self, master):
        self.size = (PREVIEW_W, PREVIEW_W * 3 // 4)
        super().__init__(master, width=self.size[0], height=self.size[1], bg="black",
                         highlightthickness=0)
        self.photo = None

    def show(self, frame):
        h, w = frame.shape[:2]
        scale = min(1.0, PREVIEW_W / w)
        size = (int(w * scale), int(h * scale))
        if size != self.size:
            self.size = size
            self.config(width=size[0], height=size[1])
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize(size)
        self.photo = ImageTk.PhotoImage(img)
        self.delete("all")
        self.create_image(0, 0, image=self.photo, anchor="nw")

    def to_screen(self, p):
        return p[0] * self.size[0], p[1] * self.size[1]

    def to_norm(self, e):
        return [min(max(e.x / self.size[0], 0.0), 1.0), min(max(e.y / self.size[1], 0.0), 1.0)]

    def draw_quad(self, corners):
        ring = [c for p in corners for c in self.to_screen(p)]
        self.create_polygon(ring, outline="lime", fill="", width=2)
        for label, p in zip(LABELS, corners):
            x, y = self.to_screen(p)
            self.create_text(x + 14, y - 14, text=label, fill="lime",
                             font=("TkDefaultFont", 11, "bold"))

    def dot(self, p, color, r=6):
        x, y = self.to_screen(p)
        self.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2)


class Step1(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.root, padding=8)
        self.app = app
        self.points = [list(p) for p in app.cfg.corners] if valid_corners(app.cfg.corners) else []
        self.drag = None  # index of the point being dragged

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Webcam:").pack(side="left")
        self.cam_box = ttk.Combobox(top, state="readonly", width=50,
                                    values=[f"{d} – {n}" for d, n in app.cams])
        self.cam_box.pack(side="left", padx=4)
        self.cam_box.bind("<<ComboboxSelected>>", self.on_camera)
        devices = [d for d, _ in app.cams]
        if app.device in devices:
            self.cam_box.current(devices.index(app.device))

        ttk.Label(self, text="Clicca i 4 angoli dell'area proiettata (in qualsiasi ordine). "
                             "Trascina i punti per correggerli.").pack(anchor="w", pady=4)
        self.preview = Preview(self)
        self.preview.pack()
        self.preview.bind("<ButtonPress-1>", self.on_press)
        self.preview.bind("<B1-Motion>", self.on_drag)
        self.preview.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=4)
        ttk.Button(bottom, text="Ricomincia", command=self.reset).pack(side="left")
        ttk.Button(bottom, text="Conferma", command=self.confirm).pack(side="left", padx=4)
        self.status = ttk.Label(bottom, text=app.camera_error)
        self.status.pack(side="left", padx=8)

    def on_camera(self, _e):
        self.points = []
        self.status["text"] = self.app.open_camera(self.app.cams[self.cam_box.current()][0])

    def draw_overlay(self, _points, _touches):
        if len(self.points) == 4:
            self.preview.draw_quad(calibration.order_corners(self.points))
        for p in self.points:
            self.preview.dot(p, "yellow")

    def on_press(self, e):
        for i, p in enumerate(self.points):
            x, y = self.preview.to_screen(p)
            if (x - e.x) ** 2 + (y - e.y) ** 2 <= GRAB_R ** 2:
                self.drag = i
                return
        if len(self.points) < 4:
            self.points.append(self.preview.to_norm(e))
            self.drag = len(self.points) - 1

    def on_drag(self, e):
        if self.drag is not None:
            self.points[self.drag] = self.preview.to_norm(e)

    def reset(self):
        self.points = []
        self.status["text"] = ""

    def confirm(self):
        if self.app.pipe is None:
            self.status["text"] = "Nessuna webcam aperta"
            return
        try:
            calibration.save(self.app.cfg, self.app.device, self.points)
        except ValueError as e:
            self.status["text"] = str(e)
            return
        except OSError as e:
            self.status["text"] = f"Errore salvataggio: {e}"
            return
        self.app.show(Step2)


class Step2(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.root, padding=8)
        self.app = app
        self.pages = []

        row = ttk.Frame(self)
        row.pack(fill="x")
        ttk.Label(row, text="Porta CDP:").pack(side="left")
        self.port = tk.StringVar(value=str(app.cfg.cdp_port))
        ttk.Entry(row, textvariable=self.port, width=8).pack(side="left", padx=4)
        ttk.Button(row, text="Collega", command=self.connect).pack(side="left")

        ttk.Label(self, text="Scheda del browser:").pack(anchor="w", pady=(8, 0))
        self.listbox = tk.Listbox(self, width=100, height=8, exportselection=False)
        self.listbox.pack(fill="x")
        self.status = ttk.Label(self, text="", wraplength=800, justify="left")
        self.status.pack(anchor="w", pady=4)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Indietro", command=lambda: app.show(Step1)).pack(side="left")
        ttk.Button(bottom, text="Avanti", command=self.next).pack(side="left", padx=4)

    def read_port(self):
        try:
            port = int(self.port.get())
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            self.status["text"] = "Porta non valida"
            return None
        return port

    def connect(self):
        self.listbox.delete(0, "end")
        self.pages = []
        port = self.read_port()
        if port is None:
            return
        try:
            self.pages = cdp.list_pages(port)
        except OSError as e:
            self.status["text"] = (f"Nessun browser sulla porta {port} ({e}).\n"
                                   f"Avvia Chromium così:\n{CHROMIUM_CMD.format(port=port)}")
            return
        for p in self.pages:
            self.listbox.insert("end", f"{p.get('title', '')} – {p.get('url', '')}")
        if len(self.pages) == 1:
            self.listbox.selection_set(0)
        self.status["text"] = f"{len(self.pages)} schede trovate" if self.pages else "Nessuna scheda aperta"

    def next(self):
        sel = self.listbox.curselection()
        if not sel:
            self.status["text"] = "Collega e scegli una scheda"
            return
        try:
            self.app.set_output(cdp.CdpOutput(self.pages[sel[0]]["webSocketDebuggerUrl"], on_command=self.app.commands.put))
        except OSError as e:
            self.status["text"] = str(e)
            return
        self.app.cfg.cdp_port = self.read_port()
        try:
            config.save(self.app.cfg)
        except OSError as e:
            self.status["text"] = f"Errore salvataggio: {e}"
            return
        self.app.show(Step3)


class Step3(ttk.Frame):
    def __init__(self, app):
        super().__init__(app.root, padding=8)
        self.app = app
        cfg = app.cfg
        self.corners = cfg.corners
        self.h = calibration.homography(self.corners)
        self.h_inv = np.linalg.inv(self.h)
        self.touch = None  # camera point of the mouse test touch
        if app.pipe is not None:
            app.pipe.homography = self.h
            app.pipe.output = app.output

        top = ttk.Frame(self)
        top.pack(fill="x")
        self.pause_btn = tk.Button(top, font=("TkDefaultFont", 14, "bold"), width=16,
                                   command=app.toggle_pause)
        self.pause_btn.pack(side="left")
        self.update_pause()
        ttk.Label(top, text="Rilevamento:").pack(side="left", padx=(12, 0))
        self.det_box = ttk.Combobox(top, state="readonly", width=14, values=list(DETECTORS))
        names = list(DETECTORS.values())
        self.det_box.current(names.index(cfg.detector) if cfg.detector in names else 0)
        self.det_box.bind("<<ComboboxSelected>>", self.on_detector)
        self.det_box.pack(side="left", padx=4)
        self.on_detector(None)

        sliders = ttk.Frame(self)
        sliders.pack(fill="x", pady=4)
        self.slider(sliders, "Confidenza minima", "min_confidence", 0.0, 1.0)
        self.slider(sliders, "Fotogrammi per entrare", "frames_in", 1, 6, integer=True)
        self.slider(sliders, "per uscire", "frames_out", 1, 15, integer=True)
        self.slider(sliders, "Smoothing (Hz, basso = più liscio)", "filter_min_cutoff", 0.1, 5.0)

        ttk.Label(self, text="Punti: verde = dentro l'area, grigio = fuori. Cerchi rossi = tocchi inviati. "
                             "Test senza visione: clicca e trascina sull'anteprima. "
                             "Nella pagina: Ctrl+Alt+P pausa, Ctrl+Alt+Q esci.").pack(anchor="w", pady=4)
        self.preview = Preview(self)
        self.preview.pack()
        self.preview.bind("<ButtonPress-1>", self.on_mouse)
        self.preview.bind("<B1-Motion>", self.on_mouse)
        self.preview.bind("<ButtonRelease-1>", self.on_release)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=4)
        ttk.Button(bottom, text="Ricalibra", command=lambda: app.show(Step1)).pack(side="left")
        ttk.Button(bottom, text="Cambia scheda", command=lambda: app.show(Step2)).pack(side="left", padx=4)
        self.status = ttk.Label(bottom, text="")
        self.status.pack(side="left", padx=8)

    def slider(self, parent, text, attr, lo, hi, integer=False):
        """Labeled slider bound to a cfg attribute; the pipeline reads cfg live."""
        cfg = self.app.cfg
        var = tk.DoubleVar(value=getattr(cfg, attr))
        fmt = (lambda v: f"{v:d}") if integer else (lambda v: f"{v:.2f}")
        value = ttk.Label(parent, text=fmt(getattr(cfg, attr)), width=5)

        def changed(_v):
            v = round(var.get()) if integer else round(var.get(), 2)
            setattr(cfg, attr, v)
            value["text"] = fmt(v)

        ttk.Label(parent, text=text).pack(side="left", padx=(0, 2))
        ttk.Scale(parent, from_=lo, to=hi, variable=var, length=110, command=changed).pack(side="left")
        value.pack(side="left", padx=(2, 10))

    def update_pause(self):
        paused = self.app.pipe is not None and self.app.pipe.paused
        self.pause_btn.config(text="Riprendi tocchi" if paused else "Pausa tocchi",
                              bg="orange" if paused else "lightgreen")

    def on_detector(self, _e):
        self.app.cfg.detector = DETECTORS[self.det_box.get()]

    def draw_overlay(self, points, touches):
        pv = self.preview
        pv.draw_quad(self.corners)
        for x, y, label in points:
            u, v = calibration.to_projection(self.h, (x, y))
            color = "lime" if 0 <= u <= 1 and 0 <= v <= 1 else "gray"
            pv.dot((x, y), color, 6)
            sx, sy = pv.to_screen((x, y))
            pv.create_text(sx, sy - 14, text=label, fill=color)
        pipe = self.app.pipe
        color = "orange" if pipe is not None and pipe.paused else "red"
        for tid, (u, v) in touches.items():
            p = calibration.to_projection(self.h_inv, (u, v))
            pv.dot(p, color, 14)
            sx, sy = pv.to_screen(p)
            pv.create_text(sx + 22, sy, text="mouse" if tid == MOUSE_ID else str(tid),
                           fill=color, font=("TkDefaultFont", 11, "bold"))
        if pipe is not None:
            state = "IN PAUSA – " if pipe.paused else ""
            self.status["text"] = state + (pipe.send_error or pipe.error or
                                           f"{pipe.fps:.0f} fps, {len(touches)} tocchi")

    def on_mouse(self, e):
        u, v = calibration.to_projection(self.h, self.preview.to_norm(e))
        if self.app.pipe is not None:
            self.app.pipe.mouse = (u, v) if 0 <= u <= 1 and 0 <= v <= 1 else None

    def on_release(self, _e):
        if self.app.pipe is not None:
            self.app.pipe.mouse = None


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = config.load()
        self.cams = camera.list_cameras()
        self.pipe = None
        self.device = None
        self.camera_error = ""
        self.output = None
        self.step = None
        self.commands = queue.Queue()  # from the page (CDP binding thread) to the UI thread

        devices = [d for d, _ in self.cams]
        if not devices:
            self.camera_error = "Nessuna webcam trovata"
        else:
            self.camera_error = self.open_camera(self.cfg.camera if self.cfg.camera in devices else devices[0])

        saved = valid_corners(self.cfg.corners) and self.device == self.cfg.camera and self.pipe is not None
        if saved and messagebox.askyesno("mat-touch", "Usare la calibrazione salvata?"):
            self.show(Step2)
        else:
            self.show(Step1)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.after(FRAME_MS, self.tick)

    def open_camera(self, device) -> str:
        """Open the webcam; return an error message, or "" on success."""
        if self.pipe is not None:
            self.pipe.stop()
            self.pipe = None
        self.device = device
        try:
            self.pipe = Pipeline(device, self.cfg)
        except OSError as e:
            return str(e)
        self.pipe.output = self.output
        return ""

    def show(self, step_cls):
        if self.step is not None:
            self.step.destroy()
        if self.pipe is not None:
            self.pipe.running = step_cls is Step3  # detect and send touches only while running
            self.pipe.mouse = None
        self.step = step_cls(self)
        self.step.pack(fill="both", expand=True)

    def set_output(self, output):
        old, self.output = self.output, output
        if self.pipe is not None:
            self.pipe.output = output
        if old is not None:
            old.close()

    def toggle_pause(self):
        if self.pipe is not None:
            self.pipe.paused = not self.pipe.paused
        if isinstance(self.step, Step3):
            self.step.update_pause()

    def tick(self):
        while not self.commands.empty():
            cmd = self.commands.get()
            if cmd == "pause":
                self.toggle_pause()
            elif cmd == "quit":
                self.quit()
                return
        preview = getattr(self.step, "preview", None)
        if self.pipe is not None and preview is not None:
            frame, points, touches = self.pipe.latest()
            if frame is not None:
                preview.show(frame)
                self.step.draw_overlay(points, touches)
        self.root.after(FRAME_MS, self.tick)

    def quit(self):
        if self.pipe is not None:
            self.pipe.stop()  # stop the sender before closing its output
        if self.output is not None:
            self.output.close()
        try:
            config.save(self.cfg)  # keep detector/slider choices
        except OSError:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    root.title("mat-touch")
    App(root)
    root.mainloop()
