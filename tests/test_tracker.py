"""Run: python -m tests.test_tracker"""
from mat_touch.filters import OneEuro2D
from mat_touch.tracker import Tracker

ARGS = dict(frames_in=2, frames_out=3, min_cutoff=1.0, beta=0.0)


def test_debounce_and_stable_ids():
    tr = Tracker()
    assert tr.update([(0.5, 0.5)], 0.0, **ARGS) == {}          # 1st frame: candidate only
    out = tr.update([(0.51, 0.5)], 0.1, **ARGS)                # 2nd frame: touch starts
    assert list(out) == [0]
    out = tr.update([(0.9, 0.9), (0.52, 0.5)], 0.2, **ARGS)    # new point does not steal id 0
    assert list(out) == [0]
    out = tr.update([(0.53, 0.5), (0.9, 0.9)], 0.3, **ARGS)
    assert sorted(out) == [0, 1]


def test_single_frame_noise_is_ignored():
    tr = Tracker()
    tr.update([(0.5, 0.5)], 0.0, **ARGS)
    assert tr.update([], 0.1, **ARGS) == {}
    assert tr.update([(0.5, 0.5)], 0.2, **ARGS) == {}  # streak restarted


def test_touch_survives_short_gaps():
    tr = Tracker()
    tr.update([(0.5, 0.5)], 0.0, **ARGS)
    tr.update([(0.5, 0.5)], 0.1, **ARGS)
    assert list(tr.update([], 0.2, **ARGS)) == [0]
    assert list(tr.update([], 0.3, **ARGS)) == [0]
    assert tr.update([], 0.4, **ARGS) == {}  # 3rd miss = frames_out: finger up


def test_far_jump_is_a_new_touch():
    tr = Tracker()
    tr.update([(0.1, 0.1)], 0.0, **ARGS)
    tr.update([(0.1, 0.1)], 0.1, **ARGS)
    out = tr.update([(0.9, 0.9)], 0.2, **ARGS)
    assert list(out) == [0]  # old touch still lingering, new one is a candidate


def test_one_euro_smooths_jitter_and_follows():
    f = OneEuro2D()
    xs = [f(i / 30, 0.5 + (0.01 if i % 2 else -0.01), 0.5, 1.0, 0.0)[0] for i in range(60)]
    assert max(xs[30:]) - min(xs[30:]) < 0.01  # jitter of 0.02 is damped
    f = OneEuro2D()
    for i in range(30):
        x, _ = f(i / 30, 0.8, 0.5, 1.0, 0.0)
    assert abs(x - 0.8) < 1e-6


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
