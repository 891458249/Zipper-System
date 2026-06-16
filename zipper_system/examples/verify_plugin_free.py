# -*- coding: utf-8 -*-
"""Standalone proof that the native build needs NO plugin (and the deformer does).

Run headless (no GUI):
    mayapy verify_plugin_free.py

Covers:
  1. native build with the plugin NEVER loaded: no ddZipperDeformer node exists,
     the node type isn't even registered, yet zip=1 converges every rail CV onto
     the mid curve and zip=0 returns to rest.
  2. native build under UNFROZEN transforms still reaches the mid's WORLD pos.
  3. delete_rig() removes every helper DG node (no orphans).
  4. contrast: a deformer build creates a ddZipperDeformer; after deleting it and
     unloading the plugin the node type is gone -- meanwhile a native rig keeps
     working with the plugin unloaded (the whole point: downstream-safe).

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

_HELPER_TYPES = ("pointOnCurveInfo", "remapValue", "blendColors",
                 "pointMatrixMult")
_FAILURES = []


def check(cond, msg):
    print("[%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _FAILURES.append(msg)


def _line(name, x, y):
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, y, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _line_local(name):
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(0.0, 0.0, z) for z in (-3, -1, 1, 3)]),
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


def _helper_count():
    return sum(len(cmds.ls(type=t) or []) for t in _HELPER_TYPES)


def _unload_zipper_plugin():
    """Unload whichever loaded plugin registered ddZipperDeformer."""
    # Deleted deformer nodes linger in the undo queue and keep the plugin "in
    # use"; flush so the unload reflects the live scene only.
    cmds.flushUndo()
    for plug in (cmds.pluginInfo(query=True, listPlugins=True) or []):
        nodes = cmds.pluginInfo(plug, query=True, dependNode=True) or []
        if "ddZipperDeformer" in nodes:
            cmds.unloadPlugin(plug)
            return plug
    return None


# --------------------------------------------------------------------------- #
# 1 + 3. native build, no plugin, converge, clean delete
# --------------------------------------------------------------------------- #
def test_native_no_plugin():
    cmds.file(new=True, force=True)
    _unload_zipper_plugin()  # make sure we truly start with no plugin
    baseline = _helper_count()

    mid = _line("midC", 0.0, 0.0)
    a, b = _line("railA", 0.0, 2.0), _line("railB", 0.0, -2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    spec = {"name": "nativeRig", "build_mode": "native", "seams": [{
        "mid": mid, "rails": [a, b], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl}]}
    root = zipper_builder.build(spec)

    check(not (cmds.ls(type="ddZipperDeformer") or []),
          "no ddZipperDeformer node created by native build")
    check("ddZipperDeformer" not in (cmds.allNodeTypes() or []),
          "plugin node type not even registered (plugin never loaded)")

    mid_pts = _cvs(mid)
    cmds.setAttr(ctrl + ".zip", 0.0)
    open_d = min(_max_dist(a, mid_pts), _max_dist(b, mid_pts))
    check(open_d > 1.0, "zip=0: rails sit at rest, away from mid (%.3f)" % open_d)

    cmds.setAttr(ctrl + ".zip", 1.0)
    closed = max(_max_dist(a, mid_pts), _max_dist(b, mid_pts))
    print("    native zip=1 worst dist to mid: %.6f" % closed)
    check(closed < 1e-4, "zip=1: both rails converge onto mid (%.2e)" % closed)

    cmds.setAttr(ctrl + ".zip", 0.0)
    back = max(_max_dist(a, mid_pts), _max_dist(b, mid_pts))
    check(abs(back - open_d) < 1e-4, "zip back to 0 returns rails to rest")

    # Clean delete: every helper DG node gone, no orphans.
    zipper_builder.delete_rig(root)
    check(not cmds.objExists(root), "rig_root deleted")
    check(_helper_count() == baseline,
          "all native helper DG nodes removed (count %d == baseline %d)"
          % (_helper_count(), baseline))


# --------------------------------------------------------------------------- #
# 2. native under unfrozen transforms
# --------------------------------------------------------------------------- #
def test_native_unfrozen():
    cmds.file(new=True, force=True)
    mid = _line_local("midC")
    a = _line_local("railA")
    cmds.setAttr(mid + ".translateX", 5.0)
    cmds.setAttr(mid + ".translateY", 2.0)
    cmds.setAttr(a + ".translateX", -4.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    spec = {"name": "unfrozenNative", "build_mode": "native", "seams": [{
        "mid": mid, "rails": [a], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrl}]}
    zipper_builder.build(spec)

    cmds.setAttr(ctrl + ".zip", 1.0)
    d = _max_dist(a, _cvs(mid))
    print("    native unfrozen zip=1 dist to mid world: %.6f" % d)
    check(d < 1e-4, "unfrozen: rail reaches mid WORLD position (%.2e)" % d)


# --------------------------------------------------------------------------- #
# 4. contrast: deformer needs the plugin; native survives its unload
# --------------------------------------------------------------------------- #
def test_deformer_needs_plugin_native_survives():
    cmds.file(new=True, force=True)

    # Native rig first (built with no plugin).
    midN = _line("midN", 0.0, 0.0)
    aN = _line("aN", 0.0, 2.0)
    ctrlN = cmds.spaceLocator(name="nCTRL")[0]
    zipper_builder.build({"name": "natRig", "build_mode": "native", "seams": [{
        "mid": midN, "rails": [aN], "feather": 0.15, "direction": "both",
        "invert": False, "controller": ctrlN}]})

    # Deformer rig (loads the plugin).
    midD = _line("midD", 10.0, 0.0)
    aD = _line("aD", 10.0, 2.0)
    ctrlD = cmds.spaceLocator(name="dCTRL")[0]
    dRoot = zipper_builder.build({"name": "defRig", "build_mode": "deformer",
        "seams": [{"mid": midD, "rails": [aD], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrlD}]})
    check(bool(cmds.ls(type="ddZipperDeformer") or []),
          "deformer build created a ddZipperDeformer node")

    # Remove the deformer rig so the plugin can unload, then unload it.
    zipper_builder.delete_rig(dRoot)
    plug = _unload_zipper_plugin()
    check(plug is not None, "zipper plugin was loaded and got unloaded")
    check("ddZipperDeformer" not in (cmds.allNodeTypes() or []),
          "after unload the deformer node type is gone (binding would vanish)")

    # The native rig keeps working with NO plugin loaded.
    cmds.setAttr(ctrlN + ".zip", 1.0)
    d = _max_dist(aN, _cvs(midN))
    print("    native rig with plugin unloaded, zip=1 dist: %.6f" % d)
    check(d < 1e-4, "native rig animates correctly with plugin unloaded (%.2e)"
          % d)


def main():
    test_native_no_plugin()
    print("")
    test_native_unfrozen()
    print("")
    test_deformer_needs_plugin_native_survives()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
