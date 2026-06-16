# -*- coding: utf-8 -*-
"""Standalone repro + regression for the mid==rail_a degeneration fix.

Run headless (no GUI):
    mayapy verify_distinct_curves.py

Covers:
  1. P0-1 selection: two curves sharing a SHORT name under different parents
     resolve to UNIQUE full DAG paths via get_selected_curve().
  2. P0-2/P1-1 reject: a seam whose mid is the same object as rail_a is refused
     by validate() AND by build() -- zero ddZipperDeformer nodes created.
  3. Regression: three distinct curves build, and at zip=1 every CV of rail A
     and rail B lands on the mid curve (||cv - nearest mid sample|| ~ 0).

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

from zipper_system.build import selection            # noqa: E402
from zipper_system.build import zipper_builder        # noqa: E402
from zipper_system.build.validate import validate     # noqa: E402


_FAILURES = []


def check(cond, msg):
    status = "PASS" if cond else "FAIL"
    print("[%s] %s" % (status, msg))
    if not cond:
        _FAILURES.append(msg)


def _line_curve(name, x):
    """A simple 4-CV line along Z at offset x; returns its transform name."""
    pts = [(x, 0.0, z) for z in (-3.0, -1.0, 1.0, 3.0)]
    crv = cmds.curve(degree=1, point=pts)
    return cmds.rename(crv, name)


def _nearest_mid_dist(cv, mid_pts):
    best = None
    for m in mid_pts:
        d = ((cv[0] - m[0]) ** 2 + (cv[1] - m[1]) ** 2
             + (cv[2] - m[2]) ** 2) ** 0.5
        if best is None or d < best:
            best = d
    return best


# --------------------------------------------------------------------------- #
# 1. P0-1: short-name collision resolves to unique full paths
# --------------------------------------------------------------------------- #
def test_selection_full_paths():
    cmds.file(new=True, force=True)
    gA = cmds.group(empty=True, name="grpA")
    cA = cmds.parent(_line_curve("dupCurve", -1.0), gA)[0]
    cA_full = cmds.ls(cA, long=True)[0]      # unique now (B not created yet)
    gB = cmds.group(empty=True, name="grpB")
    cB = cmds.parent(_line_curve("dupCurve", 1.0), gB)[0]
    cB_full = cmds.ls(cB, long=True)[0]

    # Selecting by the SHORT name is ambiguous now (the old bug's root); drive
    # selection by full path and confirm the selector hands back unique paths.
    cmds.select(cA_full, replace=True)
    pa = selection.get_selected_curve()
    cmds.select(cB_full, replace=True)
    pb = selection.get_selected_curve()

    check(pa.startswith("|"), "get_selected_curve returns full path (A): %s" % pa)
    check(pb.startswith("|"), "get_selected_curve returns full path (B): %s" % pb)
    check(pa != pb,
          "same-short-name curves resolve to DISTINCT paths: %s vs %s"
          % (pa, pb))


# --------------------------------------------------------------------------- #
# 2. P0-2 / P1-1: mid == rail_a is rejected, zero nodes created
# --------------------------------------------------------------------------- #
def test_reject_mid_equals_rail_a():
    cmds.file(new=True, force=True)
    rail_a = cmds.ls(_line_curve("railA", -2.0), long=True)[0]
    rail_b = cmds.ls(_line_curve("railB", 2.0), long=True)[0]
    # mid mis-picked as rail_a (the exact degeneration: B->A, A static).
    spec = {"name": "bad", "seams": [{
        "mid": rail_a, "rails": [rail_a, rail_b],
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": "",
    }]}

    report = validate(spec)
    check(not report.ok, "validate() rejects mid==rail_a seam")
    msgs = report.seam_errors.get(0, [])
    check(any("different curve from mid" in m for m in msgs),
          "rejection message names the mid clash: %r" % (msgs,))

    before = len(cmds.ls(type="ddZipperDeformer") or [])
    raised = False
    try:
        zipper_builder.build(spec)
    except Exception as exc:  # ZipperValidationError
        raised = True
        print("    build() refused as expected: %s"
              % str(exc).splitlines()[0])
    after = len(cmds.ls(type="ddZipperDeformer") or [])
    check(raised, "build() raises on degenerate seam")
    check(after == before,
          "ZERO ddZipperDeformer nodes created (before=%d after=%d)"
          % (before, after))


# --------------------------------------------------------------------------- #
# 3. Regression: three distinct curves -> rails converge to mid at zip=1
# --------------------------------------------------------------------------- #
def test_regression_converge_to_mid():
    cmds.file(new=True, force=True)
    rail_a = cmds.ls(_line_curve("railA", -2.0), long=True)[0]
    mid = cmds.ls(_line_curve("midC", 0.0), long=True)[0]
    rail_b = cmds.ls(_line_curve("railB", 2.0), long=True)[0]
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]

    spec = {"name": "good", "seams": [{
        "mid": mid, "rails": [rail_a, rail_b],
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": ctrl,
    }]}

    report = validate(spec)
    check(report.ok, "validate() accepts three distinct curves")

    rig_root = zipper_builder.build(spec)
    check(rig_root is not None, "build() returns a rig root")
    defs = cmds.ls(type="ddZipperDeformer") or []
    check(len(defs) == 2, "two deformers created (one per rail): %d" % len(defs))

    mid_shape = cmds.listRelatives(mid, shapes=True, fullPath=True)[0]

    def cv_world(curve):
        n = cmds.getAttr(curve + ".spans") + cmds.getAttr(curve + ".degree")
        return [tuple(cmds.pointPosition(curve + ".cv[%d]" % i, world=True))
                for i in range(n)]

    # zip = 0: rails sit apart from mid.
    cmds.setAttr(ctrl + ".zip", 0.0)
    mid_pts = cv_world(mid_shape)
    a0 = max(_nearest_mid_dist(cv, mid_pts) for cv in cv_world(rail_a))
    b0 = max(_nearest_mid_dist(cv, mid_pts) for cv in cv_world(rail_b))
    check(a0 > 1.0 and b0 > 1.0,
          "zip=0: both rails away from mid (A=%.3f B=%.3f)" % (a0, b0))

    # zip = 1: every CV of both rails lands on the mid curve.
    cmds.setAttr(ctrl + ".zip", 1.0)
    mid_pts = cv_world(mid_shape)
    a1 = max(_nearest_mid_dist(cv, mid_pts) for cv in cv_world(rail_a))
    b1 = max(_nearest_mid_dist(cv, mid_pts) for cv in cv_world(rail_b))
    print("    zip=1 max dist to mid: A=%.6f  B=%.6f" % (a1, b1))
    check(a1 < 1e-4, "zip=1: rail A converged onto mid (max=%.6e)" % a1)
    check(b1 < 1e-4, "zip=1: rail B converged onto mid (max=%.6e)" % b1)


def main():
    test_selection_full_paths()
    print("")
    test_reject_mid_equals_rail_a()
    print("")
    test_regression_converge_to_mid()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
