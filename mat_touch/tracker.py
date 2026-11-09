"""Stable touch ids across frames, with debouncing and smoothing."""
import math

from .filters import OneEuro2D

# shortcut: greedy nearest-neighbour matching; switch to the Hungarian algorithm if ids swap
# when hands cross.
MAX_DIST = 0.2  # max jump between frames, in projected-area units


class Track:
    def __init__(self, tid, x, y):
        self.id = tid
        self.x, self.y = x, y  # smoothed position
        self.seen = 1          # consecutive frames detected
        self.missing = 0       # consecutive frames not detected
        self.confirmed = False
        self.filter = OneEuro2D()


class Tracker:
    def __init__(self):
        self.tracks: list[Track] = []
        self.next_id = 0

    def reset(self):
        self.tracks = []

    def update(self, points, t, frames_in, frames_out, min_cutoff, beta) -> dict:
        """points: [(x, y)] in projected-area coords. Returns {id: (x, y)} of confirmed touches."""
        pairs = sorted((math.dist((tr.x, tr.y), p), ti, pi)
                       for ti, tr in enumerate(self.tracks) for pi, p in enumerate(points))
        used_t, used_p = set(), set()
        for d, ti, pi in pairs:
            if d > MAX_DIST:
                break
            if ti in used_t or pi in used_p:
                continue
            used_t.add(ti)
            used_p.add(pi)
            tr = self.tracks[ti]
            tr.x, tr.y = tr.filter(t, *points[pi], min_cutoff, beta)
            tr.seen += 1
            tr.missing = 0
            tr.confirmed = tr.confirmed or tr.seen >= frames_in

        keep = []
        for ti, tr in enumerate(self.tracks):
            if ti not in used_t:
                tr.missing += 1
                tr.seen = 0
                # Candidates die at the first miss; touches survive frames_out misses.
                if not tr.confirmed or tr.missing >= frames_out:
                    continue
            keep.append(tr)
        for pi, p in enumerate(points):
            if pi not in used_p:
                tr = Track(self.next_id, *p)
                tr.filter(t, *p, min_cutoff, beta)
                tr.confirmed = frames_in <= 1
                self.next_id += 1
                keep.append(tr)
        self.tracks = keep
        return {tr.id: (tr.x, tr.y) for tr in self.tracks if tr.confirmed}
