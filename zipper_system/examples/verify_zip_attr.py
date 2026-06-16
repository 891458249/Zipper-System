# -*- coding: utf-8 -*-
"""Standalone regression for the custom zip-attribute name (multi-system ctrl).

Run headless (no GUI):
    mayapy verify_zip_attr.py

Covers:
  1. Two builds on the SAME controller with zip_attr "mouthZip" / "eyeZip" each
     create a keyable double attr and connect ONLY to their own deformers.
  2. Independence: mouthZip=1/eyeZip=0 closes system 1 only; reversing closes
     system 2 only.
  3. Compatibility: an absent/blank zip_attr still creates and drives "zip".

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


def _line(name, x, y):
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, y, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _cvs(curve):
    shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
    n = cmds.getAttr(shape + ".spans") + cmds.getAttr(shape + ".degree")
    return [tuple(cmds.pointPosition(shape + ".cv[%d]" % i, world=True))
            for i in range(n)]


def _max_dist(curve, mid_pts):
    worst = 0.0
    for cv in _cvs(curve):
        best = min(((cv[0] - m[0]) ** 2 + (cv[1] - m[1]) ** 2
                    + (cv[2] - m[2]) ** 2) ** 0.5 for m in mid_pts)
        worst = max(worst, best)
    return worst


def test_two_systems_one_controller():
    cmds.file(new=True, force=True)
    ctrl = cmds.spaceLocator(name="master_CTRL")[0]

    mid1 = _line("mid1", 0.0, 0.0)
    a1, b1 = _line("a1", 0.0, 2.0), _line("b1", 0.0, -2.0)
    mid2 = _line("mid2", 20.0, 10.0)
    a2, b2 = _line("a2", 20.0, 12.0), _line("b2", 20.0, 8.0)

    zipper_builder.build({"name": "mouthSys", "seams": [{
        "mid": mid1, "rails": [a1, b1], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl, "zip_attr": "mouthZip"}]})
    zipper_builder.build({"name": "eyeSys", "seams": [{
        "mid": mid2, "rails": [a2, b2], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl, "zip_attr": "eyeZip"}]})

    for attr in ("mouthZip", "eyeZip"):
        exists = cmds.attributeQuery(attr, node=ctrl, exists=True)
        check(exists, "controller has attr %s" % attr)
        if exists:
            check(cmds.attributeQuery(attr, node=ctrl, attributeType=True)
                  == "double", "%s is a double" % attr)
            check(cmds.attributeQuery(attr, node=ctrl, keyable=True),
                  "%s is keyable" % attr)

    m_conn = set(cmds.listConnections("%s.mouthZip" % ctrl,
                                      type="ddZipperDeformer") or [])
    e_conn = set(cmds.listConnections("%s.eyeZip" % ctrl,
                                      type="ddZipperDeformer") or [])
    check(len(m_conn) == 2, "mouthZip drives 2 deformers (%d)" % len(m_conn))
    check(len(e_conn) == 2, "eyeZip drives 2 deformers (%d)" % len(e_conn))
    check(not (m_conn & e_conn), "the two systems share no deformer")

    mid1pts, mid2pts = _cvs(mid1), _cvs(mid2)
    cmds.setAttr("%s.mouthZip" % ctrl, 1.0)
    cmds.setAttr("%s.eyeZip" % ctrl, 0.0)
    s1 = max(_max_dist(a1, mid1pts), _max_dist(b1, mid1pts))
    s2 = min(_max_dist(a2, mid2pts), _max_dist(b2, mid2pts))
    print("    mouthZip=1,eyeZip=0: sys1=%.4f sys2=%.4f" % (s1, s2))
    check(s1 < 1e-4, "system 1 closed on its mid (%.2e)" % s1)
    check(s2 > 1.0, "system 2 untouched (%.3f from mid)" % s2)

    cmds.setAttr("%s.mouthZip" % ctrl, 0.0)
    cmds.setAttr("%s.eyeZip" % ctrl, 1.0)
    s1b = min(_max_dist(a1, mid1pts), _max_dist(b1, mid1pts))
    s2b = max(_max_dist(a2, mid2pts), _max_dist(b2, mid2pts))
    print("    mouthZip=0,eyeZip=1: sys1=%.4f sys2=%.4f" % (s1b, s2b))
    check(s2b < 1e-4, "system 2 closed on its mid (%.2e)" % s2b)
    check(s1b > 1.0, "system 1 reopened/untouched (%.3f)" % s1b)


def test_default_zip_attr():
    cmds.file(new=True, force=True)
    ctrl = cmds.spaceLocator(name="legacy_CTRL")[0]
    mid = _line("midL", 0.0, 0.0)
    rail = _line("aL", 0.0, 2.0)
    # No zip_attr key at all -> must behave exactly like the old "zip" default.
    zipper_builder.build({"name": "legacy", "seams": [{
        "mid": mid, "rails": [rail], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl}]})
    check(cmds.attributeQuery("zip", node=ctrl, exists=True),
          "absent zip_attr -> default 'zip' attribute created")
    deformers = cmds.listConnections("%s.zip" % ctrl,
                                     type="ddZipperDeformer") or []
    check(len(deformers) == 1, "default 'zip' drives the one deformer")


def main():
    test_two_systems_one_controller()
    print("")
    test_default_zip_attr()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
