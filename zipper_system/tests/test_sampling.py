# -*- coding: utf-8 -*-
"""Arc-length resampling + pairing (ARCHITECTURE.md sec.3.1, sec.9)."""

import pytest

from zipper_system.core import sampling as sp
from zipper_system.core.math_util import vdist


def _is_evenly_spaced(points, tol=1e-6):
    if len(points) < 3:
        return True
    d0 = vdist(points[0], points[1])
    for i in range(1, len(points) - 1):
        if abs(vdist(points[i], points[i + 1]) - d0) > tol:
            return False
    return True


def test_resample_endpoints_preserved_open():
    pts = [(0, 0, 0), (1, 0, 0), (3, 0, 0), (10, 0, 0)]
    out = sp.resample_polyline(pts, 5)
    assert out[0] == (0.0, 0.0, 0.0)
    assert out[-1] == (10.0, 0.0, 0.0)
    assert len(out) == 5


def test_resample_uniform_spacing():
    # An irregular polyline must come back evenly spaced by arc length.
    pts = [(0, 0, 0), (1, 0, 0), (1.2, 0, 0), (5, 0, 0)]
    out = sp.resample_polyline(pts, 11)
    assert _is_evenly_spaced(out)


def test_resample_degenerate_zero_length():
    pts = [(2, 2, 2), (2, 2, 2)]
    out = sp.resample_polyline(pts, 4)
    assert out == [(2, 2, 2)] * 4


def test_resample_single_point():
    out = sp.resample_polyline([(7, 8, 9)], 3)
    assert out == [(7, 8, 9)] * 3


def test_resample_closed_no_duplicate_endpoint():
    # Unit square loop, 4 samples should land on the 4 corners (no dup start).
    sq = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    out = sp.resample_polyline(sq, 4, closed=True)
    assert len(out) == 4
    assert out[0] == (0.0, 0.0, 0.0)
    # last sample is NOT the start again
    assert out[-1] != out[0]


# --- pairing: equal vs unequal length rails (sec.9) ------------------------ #
def test_pair_equal_length_rails():
    a = [(0, 1, 0), (1, 1, 0), (2, 1, 0)]
    b = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
    pairs = sp.pair_rails(a, b, 3)
    assert len(pairs) == 3
    for (pa, pb) in pairs:
        assert pa[1] == 1 and pb[1] == 0  # a above, b below


def test_pair_unequal_length_rails():
    # rail A has 2 verts, rail B has 5; arc-length pairing must still align.
    a = [(0, 1, 0), (4, 1, 0)]
    b = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0), (4, 0, 0)]
    pairs = sp.pair_rails(a, b, 5)
    assert len(pairs) == 5
    # endpoints correspond
    assert pairs[0][0][0] == pytest.approx(0.0)
    assert pairs[0][1][0] == pytest.approx(0.0)
    assert pairs[-1][0][0] == pytest.approx(4.0)
    assert pairs[-1][1][0] == pytest.approx(4.0)
    # midpoint of A (x=2) pairs with x=2 of B
    assert pairs[2][0][0] == pytest.approx(2.0)
    assert pairs[2][1][0] == pytest.approx(2.0)


def test_align_flips_reversed_rail():
    a = [(0, 1, 0), (4, 1, 0)]
    b_rev = [(4, 0, 0), (0, 0, 0)]   # authored in the opposite direction
    pairs = sp.pair_rails(a, b_rev, 2, align=True)
    # after alignment, corner 0 of A pairs with x=0 of B
    assert pairs[0][1][0] == pytest.approx(0.0)
    assert pairs[-1][1][0] == pytest.approx(4.0)


def test_resample_with_index_tracks_source_vertex():
    pts = [(0, 0, 0), (10, 0, 0)]
    samples, nearest = sp.resample_with_index(pts, 3)
    assert nearest[0] == 0
    assert nearest[-1] == 1
