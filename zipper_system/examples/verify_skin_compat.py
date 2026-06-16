# -*- coding: utf-8 -*-
"""Standalone proof that the zipper composes with skinCluster in both modes.

Run headless (no GUI):
    mayapy verify_skin_compat.py

A) deformer mode -- the zipper deformer must end up LAST on the rail chain
   (downstream of skin) so a closed CV is not re-displaced by the rail's own
   skin. Covered both for "skin first, build after" (already correct) and
   "build first, skin after -> reorder_to_chain_end fixes it".
B) native mode -- driver/output split: a hidden driver duplicate carries the
   rail's skin (live rest), the output rail is driven purely by the zipper. So
   zip=0 -> output follows the bone (== driver), zip=1 -> output == mid.

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
from zipper_system.action.zipper_action import ZipperAction  # noqa: E402

_FAILURES = []


def check(cond, msg):
    print("[%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _FAILURES.append(msg)


def _line(name, x, y):
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, y, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _shape(curve):
    return cmds.listRelatives(curve, shapes=True, fullPath=True,
                              noIntermediate=True)[0]


def _cvs(curve):
    shape = _shape(curve)
    n = cmds.getAttr(shape + ".spans") + cmds.getAttr(shape + ".degree")
    return [tuple(cmds.pointPosition(shape + ".cv[%d]" % i, world=True))
            for i in range(n)]


def _find_skin(curve):
    for n in cmds.listHistory(_shape(curve), pruneDagObjects=True) or []:
        if cmds.nodeType(n) == "skinCluster":
            return n
    return None


def _deformer_order(curve):
    """Deformers on the curve in listHistory order (last-applied first)."""
    out = []
    for n in cmds.listHistory(_shape(curve), pruneDagObjects=True) or []:
        if "geometryFilter" in (cmds.nodeType(n, inherited=True) or []):
            out.append(n)
    return out


def _dist_to_curve(curve, target_curve):
    npoc = cmds.createNode("nearestPointOnCurve")
    cmds.connectAttr(_shape(target_curve) + ".worldSpace[0]",
                     npoc + ".inputCurve", force=True)
    worst = 0.0
    for cv in _cvs(curve):
        cmds.setAttr(npoc + ".inPosition", cv[0], cv[1], cv[2])
        p = cmds.getAttr(npoc + ".position")[0]
        worst = max(worst, ((cv[0] - p[0]) ** 2 + (cv[1] - p[1]) ** 2
                            + (cv[2] - p[2]) ** 2) ** 0.5)
    cmds.delete(npoc)
    return worst


def _max_cv_delta(curve_a, curve_b):
    a, b = _cvs(curve_a), _cvs(curve_b)
    return max(((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2
                + (ca[2] - cb[2]) ** 2) ** 0.5 for ca, cb in zip(a, b))


def _skin(joint, curve):
    return cmds.skinCluster(joint, curve, toSelectedBones=True)[0]


# --------------------------------------------------------------------------- #
# A) deformer mode: zipper ends up downstream of skin
# --------------------------------------------------------------------------- #
def test_deformer_skin_first():
    cmds.file(new=True, force=True)
    j = cmds.joint(name="J0")
    cmds.select(clear=True)
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    _skin(j, mid)
    _skin(j, a)

    zipper_builder.build({"name": "defSkinFirst", "build_mode": "deformer",
        "seams": [{"mid": mid, "rails": [a], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})

    order = _deformer_order(a)
    zip_def = [d for d in order if cmds.nodeType(d) == "ddZipperDeformer"][0]
    skn = _find_skin(a)
    check(order.index(zip_def) < order.index(skn),
          "skin-first: zipper is downstream of skin (last-applied)")

    cmds.setAttr(j + ".translateY", 5.0)
    cmds.setAttr(ctrl + ".zip", 1.0)
    check(_dist_to_curve(a, mid) < 1e-4,
          "skin-first zip=1 (joint moved): railA lands on mid")
    cmds.setAttr(ctrl + ".zip", 0.0)
    ys = [cv[1] for cv in _cvs(a)]
    check(min(ys) > 6.0,
          "skin-first zip=0: railA follows the bone (y rest~2 +5 = ~7)")


def test_deformer_build_first_then_reorder():
    cmds.file(new=True, force=True)
    j = cmds.joint(name="J0")
    cmds.select(clear=True)
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]

    root = zipper_builder.build({"name": "defBuildFirst",
        "build_mode": "deformer",
        "seams": [{"mid": mid, "rails": [a], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})
    # Skin AFTER building -> wrong order; reorder fixes it.
    _skin(j, mid)
    _skin(j, a)
    reordered = ZipperAction.reorder_to_chain_end(root)
    check(len(reordered) == 1, "reorder_to_chain_end touched the zipper deformer")

    order = _deformer_order(a)
    zip_def = [d for d in order if cmds.nodeType(d) == "ddZipperDeformer"][0]
    skn = _find_skin(a)
    check(order.index(zip_def) < order.index(skn),
          "build-first+reorder: zipper now downstream of skin")

    cmds.setAttr(j + ".translateY", 5.0)
    cmds.setAttr(ctrl + ".zip", 1.0)
    check(_dist_to_curve(a, mid) < 1e-4,
          "build-first+reorder zip=1 (joint moved): railA lands on mid")


# --------------------------------------------------------------------------- #
# B) native mode: driver/output split composes with skin
# --------------------------------------------------------------------------- #
def test_native_skinned():
    cmds.file(new=True, force=True)
    j = cmds.joint(name="J0")
    cmds.select(clear=True)
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    _skin(j, mid)
    _skin(j, a)

    zipper_builder.build({"name": "natSkin", "build_mode": "native",
        "seams": [{"mid": mid, "rails": [a], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})

    drivers = cmds.ls("*_zipDriver", long=True, type="transform") or []
    check(len(drivers) == 1, "native build created one driver curve")
    driver = drivers[0]
    check(_find_skin(driver) is not None, "driver carries the skinCluster")
    check(_find_skin(a) is None, "output rail no longer has a skinCluster")

    cmds.setAttr(j + ".translateY", 5.0)
    cmds.setAttr(ctrl + ".zip", 0.0)
    d0 = _max_cv_delta(a, driver)
    print("    native zip=0 output-vs-driver max delta: %.6f" % d0)
    check(d0 < 1e-4, "native zip=0: output follows bone (== driver live pos)")
    ys = [cv[1] for cv in _cvs(a)]
    check(min(ys) > 6.0, "native zip=0: output actually moved with the bone")

    cmds.setAttr(ctrl + ".zip", 1.0)
    d1 = _dist_to_curve(a, mid)
    print("    native zip=1 dist to mid (joint moved): %.6f" % d1)
    check(d1 < 1e-4, "native zip=1: output lands on mid world position")


def test_native_unskinned_regression():
    cmds.file(new=True, force=True)
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]

    zipper_builder.build({"name": "natPlain", "build_mode": "native",
        "seams": [{"mid": mid, "rails": [a], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})

    drivers = cmds.ls("*_zipDriver", long=True, type="transform") or []
    check(len(drivers) == 1, "unskinned: static driver duplicate created")
    check(_find_skin(drivers[0]) is None, "unskinned driver has no skin")
    check(_find_skin(a) is None, "unskinned output has no skin")

    cmds.setAttr(ctrl + ".zip", 1.0)
    check(_dist_to_curve(a, mid) < 1e-4,
          "unskinned native zip=1: output lands on mid (regression)")
    cmds.setAttr(ctrl + ".zip", 0.0)
    check(_dist_to_curve(a, mid) > 1.0,
          "unskinned native zip=0: output at rest (away from mid)")


def main():
    for t in (test_deformer_skin_first,
              test_deformer_build_first_then_reorder,
              test_native_skinned,
              test_native_unskinned_regression):
        t()
        print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
