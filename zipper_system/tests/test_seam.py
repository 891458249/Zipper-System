# -*- coding: utf-8 -*-
"""Seam domain object: pairing/midline/wipe across mixed sources, multi-seam
with zero hardcoding (ARCHITECTURE.md sec.1, sec.3, sec.9)."""

import pytest

from zipper_system.core.seam import Seam
from zipper_system.core.math_util import vdist
from zipper_system.tests._fakes import FakeRail


def test_seam_midline_is_halfway():
    a = FakeRail([(0, 1, 0), (4, 1, 0)])
    b = FakeRail([(0, -1, 0), (4, -1, 0)])
    seam = Seam(a, b, pair_count=5)
    mids = seam.midline()
    assert len(mids) == 5
    for m in mids:
        assert m[1] == pytest.approx(0.0)  # midline on y=0


def test_seam_mixed_length_rails_consistent():
    # abstraction consistency: differing control-point counts still pair (R1).
    a = FakeRail([(0, 1, 0), (4, 1, 0)])                       # 2 pts
    b = FakeRail([(0, -1, 0), (2, -1, 0), (4, -1, 0)])          # 3 pts
    seam = Seam(a, b, pair_count=5)
    pairs, _da, _db = seam.sample_pairs()
    assert len(pairs) == 5
    assert pairs[0][0][0] == pytest.approx(0.0)
    assert pairs[-1][0][0] == pytest.approx(4.0)


def test_seam_aligns_reversed_rail():
    a = FakeRail([(0, 1, 0), (4, 1, 0)])
    b = FakeRail([(4, -1, 0), (0, -1, 0)])  # reversed authoring
    seam = Seam(a, b, pair_count=3)
    pairs, _da, _db = seam.sample_pairs(align=True)
    # corner 0 of A (x=0) should pair with x=0 of B after alignment
    assert pairs[0][1][0] == pytest.approx(0.0)


def test_seam_weights_endpoints():
    a = FakeRail([(0, 1, 0), (4, 1, 0)])
    b = FakeRail([(0, -1, 0), (4, -1, 0)])
    seam = Seam(a, b, pair_count=7, feather=0.15, direction="both")
    w0 = seam.weights(0.0)
    assert all(w == 0.0 for w in w0)
    whalf = seam.weights(0.5)
    assert whalf[0] == 1.0           # end closed first
    assert whalf[len(whalf) // 2] == 0.0  # center not yet


def test_multi_seam_no_hardcoding():
    # 4-petal monster mouth: 4 independent seams, no upper/lower assumption (R3).
    seams = []
    for i in range(4):
        a = FakeRail([(i, 1, 0), (i + 1, 1, 0)])
        b = FakeRail([(i, -1, 0), (i + 1, -1, 0)])
        seams.append(Seam(a, b, pair_count=4, controller="petal_%d_CTRL" % i))
    assert len(seams) == 4
    for s in seams:
        assert len(s.midline()) == 4
    # each seam carries its own controller -> independent (no coupling)
    assert seams[2].controller == "petal_2_CTRL"


def test_seam_validates_params():
    a = FakeRail([(0, 1, 0), (4, 1, 0)])
    b = FakeRail([(0, -1, 0), (4, -1, 0)])
    with pytest.raises(ValueError):
        Seam(a, b, pair_count=1)
    with pytest.raises(ValueError):
        Seam(a, b, direction="sideways")
