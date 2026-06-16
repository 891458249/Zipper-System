# -*- coding: utf-8 -*-
"""Standalone regression for variable rail count + unfrozen-transform conform.

Run headless (no GUI):
    mayapy verify_variable_rails.py

Covers:
  1. Need 1 (variable rails): one mid + THREE rails (frozen transforms) build,
     producing three deformers; at zip=1 every CV of all three rails lands on
     the mid curve.
  2. Need 3 (unfrozen transforms): mid + rails authored with identical local CVs
     but moved apart by TRANSFORM only (unfrozen). At zip=1 the rails must still
     converge onto the mid curve's WORLD position (regression for the
     object-space sampling bug -- driver world matrix lifts samples to world).
  3. Reject: mid mis-picked as a rail -> validate rejects AND build creates zero
     ddZipperDeformer nodes.

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
from zipper_system.build.validate import validate     # noqa: E402


_FAILURES = []


def check(cond, msg):
    print("[%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _FAILURES.append(msg)


def _line(name, x):
    """4-CV degree-1 line along Z at world offset x (frozen: CVs carry x)."""
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, 0.0, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _line_local(name):
    """4-CV degree-1 line along Z at the ORIGIN (x offset applied via transform
    later, i.e. unfrozen)."""
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(0.0, 0.0, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _cv_world(curve):
    shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
    n = cmds.getAttr(shape + ".spans") + cmds.getAttr(shape + ".degree")
    return [tuple(cmds.pointPosition(shape + ".cv[%d]" % i, world=True))
            for i in range(n)]


def _max_dist_to_mid(curve, mid_pts):
    worst = 0.0
    for cv in _cv_world(curve):
        best = None
        for m in mid_pts:
            d = ((cv[0] - m[0]) ** 2 + (cv[1] - m[1]) ** 2
                 + (cv[2] - m[2]) ** 2) ** 0.5
            if best is None or d < best:
                best = d
        if best > worst:
            worst = best
    return worst


# --------------------------------------------------------------------------- #
# 1. Variable rail count: one mid + three rails (frozen)
# --------------------------------------------------------------------------- #
def test_three_rails_frozen():
    cmds.file(new=True, force=True)
    mid = _line("midC", 0.0)
    rails = [_line("railA", -3.0), _line("railB", 3.0), _line("railC", -6.0)]
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    spec = {"name": "tri", "build_mode": "deformer", "seams": [{
        "mid": mid, "rails": rails,
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": ctrl,
    }]}

    check(validate(spec).ok, "validate accepts one mid + three rails")
    zipper_builder.build(spec)
    defs = cmds.ls(type="ddZipperDeformer") or []
    check(len(defs) == 3, "three deformers created (one per rail): %d" % len(defs))

    cmds.setAttr(ctrl + ".zip", 1.0)
    mid_pts = _cv_world(mid)
    worst = max(_max_dist_to_mid(r, mid_pts) for r in rails)
    print("    zip=1 worst dist to mid (3 rails): %.6f" % worst)
    check(worst < 1e-4, "zip=1: all three rails converge onto mid (%.2e)" % worst)


# --------------------------------------------------------------------------- #
# 2. Unfrozen transforms: rails must reach mid's WORLD position
# --------------------------------------------------------------------------- #
def test_unfrozen_transforms():
    cmds.file(new=True, force=True)
    mid = _line_local("midC")
    rail_a = _line_local("railA")
    rail_b = _line_local("railB")
    # Move by TRANSFORM only -> unfrozen; local CVs identical, world differs.
    cmds.setAttr(mid + ".translateX", 5.0)
    cmds.setAttr(mid + ".translateY", 2.0)
    cmds.setAttr(rail_a + ".translateX", -4.0)
    cmds.setAttr(rail_b + ".translateX", 8.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    spec = {"name": "unfrozen", "build_mode": "deformer", "seams": [{
        "mid": mid, "rails": [rail_a, rail_b],
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": ctrl,
    }]}
    zipper_builder.build(spec)

    cmds.setAttr(ctrl + ".zip", 1.0)
    mid_pts = _cv_world(mid)        # mid world X = 5, Y = 2
    a = _max_dist_to_mid(rail_a, mid_pts)
    b = _max_dist_to_mid(rail_b, mid_pts)
    print("    zip=1 unfrozen dist to mid world: A=%.6f B=%.6f" % (a, b))
    check(a < 1e-4, "unfrozen: rail A reaches mid WORLD position (%.2e)" % a)
    check(b < 1e-4, "unfrozen: rail B reaches mid WORLD position (%.2e)" % b)


# --------------------------------------------------------------------------- #
# 3. Reject: mid mis-picked as a rail
# --------------------------------------------------------------------------- #
def test_reject_mid_as_rail():
    cmds.file(new=True, force=True)
    mid = _line("midC", 0.0)
    rail_b = _line("railB", 3.0)
    spec = {"name": "bad", "build_mode": "deformer", "seams": [{
        "mid": mid, "rails": [mid, rail_b],     # mid duplicated as a rail
        "feather": 0.15, "direction": "both", "invert": False, "controller": "",
    }]}

    report = validate(spec)
    check(not report.ok, "validate rejects mid duplicated as a rail")
    check(any("different curve from mid" in m
              for m in report.seam_errors.get(0, [])),
          "rejection message names the mid clash")

    before = len(cmds.ls(type="ddZipperDeformer") or [])
    raised = False
    try:
        zipper_builder.build(spec)
    except Exception as exc:
        raised = True
        print("    build refused: %s" % str(exc).splitlines()[0])
    after = len(cmds.ls(type="ddZipperDeformer") or [])
    check(raised, "build raises on degenerate seam")
    check(after == before, "ZERO deformer nodes created (%d -> %d)"
          % (before, after))


def main():
    test_three_rails_frozen()
    print("")
    test_unfrozen_transforms()
    print("")
    test_reject_mid_as_rail()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
