# -*- coding: utf-8 -*-
"""Standalone proof that the native build is correct on curves WITH history.

Run headless (no GUI):
    mayapy verify_native_history.py

Background: the native build drives railShape.controlPoints[cv] with absolute
local coords. controlPoints is absolute only on a history-free curve; with
construction history it is a TWEAK on top of .create, so an absolute value would
double (rest+rest) -> the rail jumps to ~2x rest (looks vanished) and the zip
slider seems dead. The fix deletes each rail's history before wiring.

Covers:
  1. History case (cmds.circle, carries makeNurbCircle): build_mode="native"
     with unfrozen translate; at zip=0 the rail CVs sit at REST (NOT doubled),
     at zip=1 both rails converge onto the mid curve (and on each other).
  2. The pre-fix failure is demonstrated directly: connecting absolute rest into
     a history-bearing curve's controlPoints doubles the CV (rest -> ~2x).
  3. Regression: history-free curves (cmds.curve) still build correctly.

Py2.7-safe (no f-strings); also runs under Py3.
"""
from __future__ import absolute_import, division, print_function

import os
import sys

import maya.standalone
maya.standalone.initialize(name="python")

from maya import cmds  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from zipper_system.build import zipper_builder        # noqa: E402

_FAILURES = []


def check(cond, msg):
    print("[%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _FAILURES.append(msg)


def _circle(name, ty):
    """A NURBS circle (carries makeNurbCircle history), translated in Y."""
    crv = cmds.circle(name=name, normal=(0, 0, 1), radius=2.0, sections=8)[0]
    crv = cmds.ls(crv, long=True)[0]
    cmds.setAttr(crv + ".translateY", ty)
    return crv


def _line(name, x, y):
    """A history-free degree-1 curve along Z."""
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, y, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _shape(curve):
    return cmds.listRelatives(curve, shapes=True, fullPath=True)[0]


def _cvs(curve):
    shape = _shape(curve)
    n = cmds.getAttr(shape + ".spans") + cmds.getAttr(shape + ".degree")
    return [tuple(cmds.pointPosition(shape + ".cv[%d]" % i, world=True))
            for i in range(n)]


def _has_history(curve):
    return bool(cmds.listConnections(_shape(curve) + ".create",
                                     source=True, destination=False))


def _max_pair_dist(curve_a, curve_b):
    """Worst CV-to-nearest distance between two equal-length CV sets."""
    a, b = _cvs(curve_a), _cvs(curve_b)
    worst = 0.0
    for ca in a:
        best = min(((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2
                    + (ca[2] - cb[2]) ** 2) ** 0.5 for cb in b)
        worst = max(worst, best)
    return worst


def _max_dist_to_curve(curve, target_curve):
    """Worst distance from curve's CVs to the *target_curve* itself.

    A NURBS curve's CVs lie off the curve (on the control hull), so we measure
    each rail CV against the EXACT nearest point ON the mid curve (via a
    nearestPointOnCurve node) -- the real "lands on mid" criterion, not equality
    with mid's control vertices.
    """
    npoc = cmds.createNode("nearestPointOnCurve")
    cmds.connectAttr(_shape(target_curve) + ".worldSpace[0]",
                     npoc + ".inputCurve", force=True)
    worst = 0.0
    for cv in _cvs(curve):
        cmds.setAttr(npoc + ".inPosition", cv[0], cv[1], cv[2])
        p = cmds.getAttr(npoc + ".position")[0]
        d = ((cv[0] - p[0]) ** 2 + (cv[1] - p[1]) ** 2
             + (cv[2] - p[2]) ** 2) ** 0.5
        worst = max(worst, d)
    cmds.delete(npoc)
    return worst


# --------------------------------------------------------------------------- #
# 2. Demonstrate the pre-fix doubling on a history-bearing curve.
# --------------------------------------------------------------------------- #
def test_doubling_repro_without_fix():
    cmds.file(new=True, force=True)
    crv = _circle("reproCRV", 0.0)
    shape = _shape(crv)
    rest = cmds.pointPosition(shape + ".cv[0]", world=True)
    check(_has_history(crv), "circle has construction history (.create driven)")
    # Connect the absolute rest into controlPoints[0] WITHOUT deleting history.
    loc = cmds.spaceLocator(name="restSrc")[0]
    cmds.setAttr(loc + ".translate", rest[0], rest[1], rest[2])
    cmds.connectAttr(loc + ".translate", shape + ".controlPoints[0]", force=True)
    doubled = cmds.pointPosition(shape + ".cv[0]", world=True)
    ratio = (doubled[0] ** 2 + doubled[1] ** 2 + doubled[2] ** 2) ** 0.5 / (
        (rest[0] ** 2 + rest[1] ** 2 + rest[2] ** 2) ** 0.5 or 1.0)
    print("    history+absolute controlPoints: rest=%.3f -> cv=%.3f (ratio %.2f)"
          % (rest[0], doubled[0], ratio))
    check(abs(ratio - 2.0) < 1e-3,
          "pre-fix: absolute value on history curve DOUBLES the CV (~2x rest)")


# --------------------------------------------------------------------------- #
# 1. Native build correct on history-bearing curves.
# --------------------------------------------------------------------------- #
def test_native_on_history_curves():
    cmds.file(new=True, force=True)
    mid = _circle("midC", 0.0)
    a = _circle("railA", 3.0)
    b = _circle("railB", -3.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]

    rest_a = _cvs(a)
    rest_b = _cvs(b)

    zipper_builder.build({"name": "histRig", "build_mode": "native", "seams": [{
        "mid": mid, "rails": [a, b], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl}]})

    # The fix removed the rails' history (mid keeps its own).
    check(not _has_history(a), "rail A history deleted by native build")
    check(not _has_history(b), "rail B history deleted by native build")
    check(_has_history(mid), "mid history PRESERVED (read-only driver)")

    # zip=0: rails at rest, NOT doubled / vanished.
    cmds.setAttr(ctrl + ".zip", 0.0)

    def _drift(cur, ref):
        return max(((c[0] - r[0]) ** 2 + (c[1] - r[1]) ** 2
                    + (c[2] - r[2]) ** 2) ** 0.5 for c, r in zip(cur, ref))

    da = _drift(_cvs(a), rest_a)
    db = _drift(_cvs(b), rest_b)
    print("    zip=0 drift from rest: A=%.6f B=%.6f" % (da, db))
    check(da < 1e-4 and db < 1e-4,
          "zip=0: rails stay at rest (no doubling/vanishing)")

    # zip=1: both rails converge onto the mid curve (and thus onto each other).
    cmds.setAttr(ctrl + ".zip", 1.0)
    da1 = _max_dist_to_curve(a, mid)
    db1 = _max_dist_to_curve(b, mid)
    ab1 = _max_pair_dist(a, b)
    print("    zip=1 dist to mid: A=%.6f B=%.6f ; A<->B=%.6f" % (da1, db1, ab1))
    check(da1 < 1e-4, "zip=1: rail A converges onto mid (%.2e)" % da1)
    check(db1 < 1e-4, "zip=1: rail B converges onto mid (%.2e)" % db1)
    check(ab1 < 1e-4, "zip=1: rails A and B coincide (%.2e)" % ab1)


# --------------------------------------------------------------------------- #
# 3. Regression: history-free curves still correct.
# --------------------------------------------------------------------------- #
def test_native_on_history_free_curves():
    cmds.file(new=True, force=True)
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    b = _line("railB", 0.0, -2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    check(not _has_history(a), "history-free curve has no history (precondition)")

    zipper_builder.build({"name": "plainRig", "build_mode": "native", "seams": [{
        "mid": mid, "rails": [a, b], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl}]})

    cmds.setAttr(ctrl + ".zip", 1.0)
    da = _max_dist_to_curve(a, mid)
    db = _max_dist_to_curve(b, mid)
    print("    history-free zip=1 dist to mid: A=%.6f B=%.6f" % (da, db))
    check(da < 1e-4 and db < 1e-4,
          "history-free regression: both rails converge onto mid")


def main():
    test_doubling_repro_without_fix()
    print("")
    test_native_on_history_curves()
    print("")
    test_native_on_history_free_curves()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
