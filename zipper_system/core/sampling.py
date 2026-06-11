# -*- coding: utf-8 -*-
"""Arc-length resampling and rail pairing (ARCHITECTURE.md sec.3.1).

Pure Python: input/output are lists of 3-tuples. This removes the prototype's
"both rails must have equal vertex counts" assumption -- each rail is
re-parameterised by cumulative chord length, then both are sampled at the same
normalized parameters t_k = k / (N - 1).
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from .math_util import vdist, vlerp


def cumulative_lengths(points, closed=False):
    # type: (list, bool) -> tuple
    """Return (cumulative_arc_lengths, total_length).

    cumulative[i] is the arc length from points[0] to points[i]. When closed,
    a final wrap segment points[-1]->points[0] is appended, so len(cumulative)
    == len(points) + 1 and total includes the closing segment.
    """
    if not points:
        return [], 0.0
    cum = [0.0]
    total = 0.0
    for i in range(1, len(points)):
        total += vdist(points[i - 1], points[i])
        cum.append(total)
    if closed and len(points) > 1:
        total += vdist(points[-1], points[0])
        cum.append(total)
    return cum, total


def _point_at_arclen(points, cum, s, closed=False):
    # type: (list, list, float, bool) -> tuple
    """Interpolate the polyline at absolute arc length s; return (point, seg_i,
    frac) where the sample lies on segment seg_i between vertex seg_i and the
    next, at fractional position frac in [0, 1].
    """
    m = len(points)
    if m == 1:
        return points[0], 0, 0.0
    total = cum[-1]
    if s <= 0.0:
        return points[0], 0, 0.0
    if s >= total:
        # Last reachable vertex: for closed loops that wraps to start.
        if closed:
            return points[0], m - 1, 1.0
        return points[-1], m - 2, 1.0
    # Linear scan (rails are small N); binary search is overkill here.
    seg_count = len(cum) - 1
    for i in range(seg_count):
        if cum[i] <= s <= cum[i + 1]:
            seg_len = cum[i + 1] - cum[i]
            frac = 0.0 if seg_len <= 1e-12 else (s - cum[i]) / seg_len
            a = points[i]
            b = points[i + 1] if (i + 1) < m else points[0]
            return vlerp(a, b, frac), i, frac
    return points[-1], m - 2, 1.0


def resample_polyline(points, n, closed=False):
    # type: (list, int, bool) -> list
    """Resample an ordered point list into n points evenly spaced by arc length.

    Open: n points at t_k = k/(n-1), including both endpoints.
    Closed: n points at t_k = k/n over [0, L) (no duplicated endpoint).
    Degenerate (zero length / single point): returns n copies of points[0].
    """
    out, _idx = resample_with_index(points, n, closed)
    return out


def resample_with_index(points, n, closed=False):
    # type: (list, int, bool) -> tuple
    """Like resample_polyline but also returns, per sample, the nearest source
    vertex index (useful to carry edge vertex-id bind handles through a resample).
    Returns (sample_points, nearest_source_index).
    """
    if n < 1:
        raise ValueError("n must be >= 1, got %r" % (n,))
    if not points:
        raise ValueError("cannot resample an empty point list")
    if len(points) == 1 or n == 1:
        return [points[0]] * n, [0] * n

    cum, total = cumulative_lengths(points, closed)
    m = len(points)
    if total <= 1e-12:
        return [points[0]] * n, [0] * n

    samples = []
    nearest = []
    if closed:
        denom = float(n)
    else:
        denom = float(n - 1)
    for k in range(n):
        t = k / denom
        s = t * total
        pt, seg_i, frac = _point_at_arclen(points, cum, s, closed)
        samples.append(pt)
        # Nearest original vertex index for bind-handle carry-through.
        if frac < 0.5:
            src = seg_i
        else:
            src = (seg_i + 1) % m if closed else min(seg_i + 1, m - 1)
        nearest.append(src)
    return samples, nearest


def align_rails(points_a, points_b):
    # type: (list, list) -> list
    """Return points_b possibly reversed so its start corresponds to points_a's
    start, minimizing corner cross-over when the two rails were authored in
    opposite directions. Pure heuristic on endpoint distances; points_a is the
    reference and is never modified.
    """
    if len(points_a) < 2 or len(points_b) < 2:
        return list(points_b)
    a0, a1 = points_a[0], points_a[-1]
    b0, b1 = points_b[0], points_b[-1]
    same_dir = vdist(a0, b0) + vdist(a1, b1)
    flipped = vdist(a0, b1) + vdist(a1, b0)
    if flipped < same_dir:
        return list(reversed(points_b))
    return list(points_b)


def pair_rails(points_a, points_b, n,
               closed_a=False, closed_b=False, align=True):
    # type: (list, list, int, bool, bool, bool) -> list
    """Resample both rails to n points each and zip them into pairs.

    Returns a list of (a_k, b_k) tuples of 3D points -- the input to the midline
    / wipe stages. With align=True, rail B is endpoint-aligned to rail A first
    (open rails only) so a_k and b_k share the same corner.
    """
    ra = resample_polyline(points_a, n, closed_a)
    rb = resample_polyline(points_b, n, closed_b)
    if align and not closed_a and not closed_b:
        rb = align_rails(ra, rb)
    return list(zip(ra, rb))
