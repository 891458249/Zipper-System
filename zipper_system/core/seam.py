# -*- coding: utf-8 -*-
"""Seam: a pairing of two rails closed along their midline (ARCHITECTURE.md
sec.1 / sec.3).

A Seam owns two RailSources plus the per-seam closure parameters. It is pure
domain logic: given the two rails it produces paired samples, midline points and
wipe weights, all independent of whether the rails came from edges or curves and
independent of which closure mechanic (dynamic / morph) the build layer chooses.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from .sampling import align_rails
from .math_util import midpoint, wipe_weight

VALID_DIRECTIONS = ("both", "ltr", "rtl")


class Seam(object):
    """Two rails paired along a midline.

    rail_a, rail_b : RailSource
    pair_count     : int sampling density N (>= 2)
    feather        : float wipe band beta
    direction      : 'both' | 'ltr' | 'rtl'
    invert         : reverse the wipe order (see math_util.wipe_weight)
    controller     : str name of this seam's driving controller (build/UI use)
    """

    def __init__(self, rail_a, rail_b, pair_count=30, feather=0.15,
                 direction="both", invert=False, controller=""):
        if direction not in VALID_DIRECTIONS:
            raise ValueError(
                "direction must be one of %r, got %r"
                % (VALID_DIRECTIONS, direction)
            )
        if pair_count < 2:
            raise ValueError("pair_count must be >= 2, got %r" % (pair_count,))
        self.rail_a = rail_a
        self.rail_b = rail_b
        self.pair_count = int(pair_count)
        self.feather = float(feather)
        self.direction = direction
        self.invert = bool(invert)
        self.controller = controller

    # -- sampling ----------------------------------------------------------- #
    def sample_pairs(self, align=True):
        """Return (pairs, rail_data_a, rail_data_b).

        pairs is a list of (a_k, b_k) world-point tuples. Both rails are sampled
        at pair_count, then B is endpoint-aligned to A so a_k / b_k share the
        same corner (open rails only).
        """
        n = self.pair_count
        da = self.rail_a.sample(n)
        db = self.rail_b.sample(n)
        pa = list(da.points)
        pb = list(db.points)
        if align:
            aligned = align_rails(pa, pb)
            if aligned != pb:
                pb = aligned
                db_bind = list(reversed(db.bind))
            else:
                db_bind = list(db.bind)
        else:
            db_bind = list(db.bind)
        pairs = list(zip(pa, pb))
        return pairs, da, (pb, db_bind)

    def midline(self, align=True):
        """Return the list of midline points m_k = 1/2 (a_k + b_k)."""
        pairs, _da, _db = self.sample_pairs(align)
        return [midpoint(a, b) for (a, b) in pairs]

    # -- wipe --------------------------------------------------------------- #
    def weights(self, z):
        # type: (float) -> list
        """Per-pair closure weights w_k(z) for the current parameters."""
        n = self.pair_count
        return [
            wipe_weight(k, n, z, self.feather, self.direction, self.invert)
            for k in range(n)
        ]
