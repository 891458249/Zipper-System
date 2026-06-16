# -*- coding: utf-8 -*-
"""The native build bakes the wipe into a remapValue ramp (inputMin, inputMax).

These tests prove that ramp reproduces the deformer's wipe_weight EXACTLY, so
the plugin-free build is visually identical to the deformer build. Pure math,
no Maya.
"""
from __future__ import absolute_import, division, print_function

from zipper_system.core.math_util import (
    clamp, wipe_weight, wipe_ramp_bounds)


def _remap(lo, hi, z):
    """What a remapValue node computes: linear ramp lo..hi -> 0..1, clamped."""
    if hi <= lo:
        return 1.0 if z >= hi else 0.0
    return clamp((z - lo) / (hi - lo), 0.0, 1.0)


_GRID = [
    (n, beta, direction, invert)
    for n in (2, 3, 5, 8)
    for beta in (0.05, 0.15, 0.5, 1.0)
    for direction in ("both", "ltr", "rtl")
    for invert in (False, True)
]


def test_ramp_matches_wipe_weight():
    zs = [i / 20.0 for i in range(21)]  # 0.0 .. 1.0
    for n, beta, direction, invert in _GRID:
        for k in range(n):
            lo, hi = wipe_ramp_bounds(k, n, beta, direction, invert)
            for z in zs:
                expected = wipe_weight(k, n, z, beta, direction, invert)
                got = _remap(lo, hi, z)
                assert abs(got - expected) < 1e-9, (
                    "k=%d n=%d beta=%s dir=%s inv=%s z=%s: %s != %s"
                    % (k, n, beta, direction, invert, z, got, expected))


def test_full_close_at_z1():
    # hi <= 1 always, so z = 1 fully closes every CV (lands exactly on mid).
    for n, beta, direction, invert in _GRID:
        for k in range(n):
            lo, hi = wipe_ramp_bounds(k, n, beta, direction, invert)
            assert hi <= 1.0 + 1e-12
            assert _remap(lo, hi, 1.0) == 1.0


def test_nothing_closed_at_z0():
    # At z = 0 nothing is closed (matches wipe_weight's z=0 behaviour).
    for n, beta, direction, invert in _GRID:
        for k in range(n):
            assert wipe_weight(k, n, 0.0, beta, direction, invert) == 0.0


def test_hard_step_when_no_feather():
    # beta <= 0: razor-thin ramp ending at the threshold -> steps like the
    # deformer (w = 1 iff z >= t).
    for n in (3, 5):
        for direction in ("both", "ltr", "rtl"):
            for k in range(n):
                lo, hi = wipe_ramp_bounds(k, n, 0.0, direction, False)
                assert _remap(lo, hi, 1.0) == 1.0
