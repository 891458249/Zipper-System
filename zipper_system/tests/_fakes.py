# -*- coding: utf-8 -*-
"""Maya-free test doubles."""

from zipper_system.core.rail import RailData, RailSource
from zipper_system.core.sampling import resample_with_index
from zipper_system.core.math_util import normalize, vsub


class FakeRail(RailSource):
    """A RailSource backed by an in-memory polyline -- no Maya required.

    Resamples its control points by arc length on sample() so Seam tests can run
    headless (covers the 'curve+edge mixed seam' abstraction-consistency case
    from sec.9 without a live Maya).
    """

    def __init__(self, points, closed=False):
        self._points = [tuple(p) for p in points]
        self._closed = closed

    def sample(self, n):
        pts, nearest = resample_with_index(self._points, n, self._closed)
        return RailData(pts, list(nearest))

    def tangent_at(self, i):
        p = self._points
        if len(p) < 2:
            return (0.0, 0.0, 0.0)
        j = min(max(i, 0), len(p) - 1)
        if j == 0:
            return normalize(vsub(p[1], p[0]))
        if j == len(p) - 1:
            return normalize(vsub(p[-1], p[-2]))
        return normalize(vsub(p[j + 1], p[j - 1]))

    def bind_handle(self):
        return list(range(len(self._points)))
