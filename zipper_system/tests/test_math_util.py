# -*- coding: utf-8 -*-
"""Wipe math + vector helpers (ARCHITECTURE.md sec.3.2 / sec.3.3, sec.9)."""

import pytest

from zipper_system.core import math_util as mu


def test_clamp_and_lerp():
    assert mu.clamp(-1.0) == 0.0
    assert mu.clamp(2.0) == 1.0
    assert mu.clamp(0.3) == 0.3
    assert mu.lerp(0.0, 10.0, 0.5) == 5.0


def test_midpoint():
    assert mu.midpoint((0, 0, 0), (2, 4, 6)) == (1.0, 2.0, 3.0)


def test_vlerp():
    assert mu.vlerp((0, 0, 0), (10, 0, 0), 0.25) == (2.5, 0.0, 0.0)


# --- wipe: z endpoints (sec.9: z = 0 / 0.5 / 1) ---------------------------- #
def test_wipe_z0_nothing_closed_both():
    n = 7
    for k in range(n):
        assert mu.wipe_weight(k, n, 0.0, 0.15, "both") == 0.0


def test_wipe_default_closes_ends_first():
    # sec.3.3 corrected default: ends close before the center.
    n = 7
    beta = 0.15
    z = 0.5
    w_end = mu.wipe_weight(0, n, z, beta, "both")
    w_mid = mu.wipe_weight(n // 2, n, z, beta, "both")
    assert w_end == 1.0
    assert w_mid == 0.0
    assert w_end > w_mid


def test_wipe_invert_closes_center_first():
    # invert=True restores the blueprint's printed center->ends curve.
    n = 7
    beta = 0.15
    z = 0.1
    w_end = mu.wipe_weight(0, n, z, beta, "both", invert=True)
    w_mid = mu.wipe_weight(n // 2, n, z, beta, "both", invert=True)
    assert w_mid > w_end


def test_wipe_monotonic_in_z():
    n = 9
    beta = 0.2
    for k in range(n):
        prev = -1.0
        for i in range(11):
            z = i / 10.0
            w = mu.wipe_weight(k, n, z, beta, "both")
            assert w >= prev - 1e-9  # non-decreasing in z
            prev = w


def test_wipe_directional_ltr_sweeps_left_to_right():
    n = 9
    beta = 0.1
    z = 0.5
    w_left = mu.wipe_weight(0, n, z, beta, "ltr")
    w_right = mu.wipe_weight(n - 1, n, z, beta, "ltr")
    assert w_left > w_right  # left corner closes earlier


def test_wipe_directional_rtl_is_mirror_of_ltr():
    n = 9
    beta = 0.1
    z = 0.5
    w_ltr_left = mu.wipe_weight(0, n, z, beta, "ltr")
    w_rtl_right = mu.wipe_weight(n - 1, n, z, beta, "rtl")
    assert w_ltr_left == pytest.approx(w_rtl_right)


def test_wipe_beta_zero_is_step():
    n = 5
    # ltr threshold for k=0 is 0 -> closes for any z >= 0.
    assert mu.wipe_weight(0, n, 0.0, 0.0, "ltr") == 1.0
    # k=n-1 threshold is 1 -> only closes at z >= 1.
    assert mu.wipe_weight(n - 1, n, 0.99, 0.0, "ltr") == 0.0
    assert mu.wipe_weight(n - 1, n, 1.0, 0.0, "ltr") == 1.0


def test_wipe_bad_direction_raises():
    with pytest.raises(ValueError):
        mu.wipe_threshold(0, 5, "diagonal")
