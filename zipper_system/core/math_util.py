# -*- coding: utf-8 -*-
"""Pure math helpers: vectors, midline and the wipe weight (ARCHITECTURE.md
sec.3.2 / sec.3.3).

No Maya, no Qt. Points are plain 3-tuples/lists of floats so every function is
unit-testable and CLI-callable.
"""

# Python 3.7-common syntax only.

Vec3 = "tuple"  # documentation alias; runtime stays plain tuples/lists.


# --------------------------------------------------------------------------- #
# Scalars
# --------------------------------------------------------------------------- #
def clamp(x, lo=0.0, hi=1.0):
    # type: (float, float, float) -> float
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def lerp(a, b, t):
    # type: (float, float, float) -> float
    return a + (b - a) * t


# --------------------------------------------------------------------------- #
# 3D vectors (plain tuples)
# --------------------------------------------------------------------------- #
def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vscale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vlength(a):
    return (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5


def vdist(a, b):
    return vlength(vsub(a, b))


def vlerp(a, b, t):
    """Component-wise linear interpolation between two 3D points."""
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def midpoint(a, b):
    """Midline point m_k = 1/2 (a_k + b_k)  (ARCHITECTURE.md sec.3.2)."""
    return vlerp(a, b, 0.5)


def normalize(a):
    n = vlength(a)
    if n <= 1e-12:
        return (0.0, 0.0, 0.0)
    inv = 1.0 / n
    return (a[0] * inv, a[1] * inv, a[2] * inv)


# --------------------------------------------------------------------------- #
# Wipe weight (ARCHITECTURE.md sec.3.3)
#
# BLUEPRINT CONTRADICTION RESOLUTION
# ----------------------------------
# sec.3.3 prints the formula  w_k = clamp((z - (1 - d_k)) / beta, 0, 1)  while
# its prose says the zipper closes "from both ends toward the center". Those two
# disagree: with `1 - d_k` the center (d_k=1) closes first and the ends last,
# i.e. center -> ends, the opposite of the prose and of the zipper metaphor.
#
# Per the maintainer's decision we EXPOSE BOTH directions via an `invert` flag
# and DEFAULT to the prose behavior ("ends -> center") using the corrected
# threshold  t_k = d_k  ->  w_k = clamp((z - d_k) / beta, 0, 1):
#   * ends   (d_k = 0) start closing at z = 0  -> close first
#   * center (d_k = 1) start closing at z = 1  -> close last
# Setting invert=True restores the blueprint's printed "center -> ends" curve.
#
# Directional modes (ltr / rtl) use a monotonic progress coordinate instead of
# the symmetric distance, so closure sweeps across the seam in one direction.
# --------------------------------------------------------------------------- #
def wipe_threshold(k, n, direction="both", invert=False):
    # type: (int, int, str, bool) -> float
    """Per-pair closing threshold t_k in [0, 1]; pair k closes as z passes t_k.

    direction:
        'both' -> symmetric: ends close first, center last (sec.3.3, corrected).
        'ltr'  -> sweeps k=0 .. k=n-1 (left corner first).
        'rtl'  -> sweeps k=n-1 .. k=0 (right corner first).
    invert flips the threshold (1 - t_k), reversing the closing order.
    """
    if n <= 1:
        return 0.0
    nm1 = float(n - 1)
    if direction == "both":
        half = nm1 / 2.0
        if half <= 0.0:
            t = 0.0
        else:
            # d_k: normalized distance to the nearest endpoint (0 ends, 1 mid).
            d = min(k, (n - 1) - k) / half
            t = d
    elif direction == "ltr":
        t = k / nm1
    elif direction == "rtl":
        t = ((n - 1) - k) / nm1
    else:
        raise ValueError(
            "direction must be 'both' | 'ltr' | 'rtl', got %r" % (direction,)
        )
    if invert:
        t = 1.0 - t
    return t


def wipe_weight(k, n, z, beta, direction="both", invert=False):
    # type: (int, int, float, float, str, bool) -> float
    """Closure weight w_k(z) in [0, 1] for pair k.

    w = clamp((z - t_k) / beta, 0, 1). beta <= 0 degenerates to a hard step at
    t_k. This is the spatial/temporal factor that multiplies envelope * paint in
    the deformer and is baked into the morph weight map.
    """
    t = wipe_threshold(k, n, direction, invert)
    if beta <= 0.0:
        return 1.0 if z >= t else 0.0
    return clamp((z - t) / beta, 0.0, 1.0)
