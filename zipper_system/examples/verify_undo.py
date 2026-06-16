# -*- coding: utf-8 -*-
"""Standalone proof that every zipper operation reverts with ONE undo.

Run headless (no GUI):
    mayapy verify_undo.py

build (native + deformer), delete_rig, and reorder_to_chain_end each run inside a
single undo chunk, so one cmds.undo() fully reverts them -- no orphan helper /
driver / deformer nodes, original rail history/skin restored.

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

cmds.undoInfo(state=True, infinity=True)

_FAILURES = []


def check(cond, msg):
    print("[%s] %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        _FAILURES.append(msg)


def _line(name, x, y):
    return cmds.ls(cmds.curve(name=name, degree=1,
                              point=[(x, y, z) for z in (-3, -1, 1, 3)]),
                   long=True)[0]


def _node_count():
    return len(cmds.ls(long=True) or [])


def _zipper_helper_count():
    types = ("ddZipperDeformer", "pointOnCurveInfo", "remapValue",
             "blendColors", "pointMatrixMult")
    n = sum(len(cmds.ls(type=t) or []) for t in types)
    n += len(cmds.ls("*_zipDriver", long=True) or [])
    n += len(cmds.ls("*_zipperRig", long=True) or [])
    return n


def _build(mode):
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    b = _line("railB", 0.0, -2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    return zipper_builder.build({"name": "undoRig", "build_mode": mode,
        "seams": [{"mid": mid, "rails": [a, b], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})


def test_build_undo(mode):
    cmds.file(new=True, force=True)
    # baseline scene (curves + ctrl) before the build, so undo should return here
    mid = _line("midC", 0.0, 0.0)
    a = _line("railA", 0.0, 2.0)
    b = _line("railB", 0.0, -2.0)
    ctrl = cmds.spaceLocator(name="zipCTRL")[0]
    base = _node_count()

    root = zipper_builder.build({"name": "undoRig", "build_mode": mode,
        "seams": [{"mid": mid, "rails": [a, b], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})
    check(_zipper_helper_count() > 0, "%s build created zipper nodes" % mode)

    cmds.undo()
    check(not cmds.objExists(root), "%s build: rig_root gone after 1 undo" % mode)
    check(_zipper_helper_count() == 0,
          "%s build: ZERO zipper helper/driver/deformer nodes after undo" % mode)
    check(_node_count() == base,
          "%s build: node count back to baseline (%d == %d)"
          % (mode, _node_count(), base))


def test_delete_rig_undo():
    cmds.file(new=True, force=True)
    root = _build("native")
    before = _zipper_helper_count()
    ZipperAction.delete_rig(root)
    check(not cmds.objExists(root), "delete_rig removed the rig")
    cmds.undo()
    check(cmds.objExists(root), "delete_rig: rig_root restored after 1 undo")
    check(_zipper_helper_count() == before,
          "delete_rig: all helper/driver nodes restored after undo (%d == %d)"
          % (_zipper_helper_count(), before))


def test_reorder_undo():
    cmds.file(new=True, force=True)
    j = cmds.joint(name="J0")
    cmds.select(clear=True)
    root = _build("deformer")
    # skin AFTER build -> wrong order; reorder fixes it; undo restores it.
    a = cmds.ls("railA", long=True)[0]
    cmds.skinCluster(j, a, toSelectedBones=True)
    ash = cmds.listRelatives(a, shapes=True, fullPath=True, noIntermediate=True)[0]

    def order():
        return [cmds.nodeType(n) for n in (cmds.listHistory(ash, pdo=True) or [])
                if "geometryFilter" in (cmds.nodeType(n, inherited=True) or [])]

    before = order()
    ZipperAction.reorder_to_chain_end(root)
    after = order()
    check(after != before, "reorder changed the deformer order")
    cmds.undo()
    check(order() == before, "reorder: deformer order restored after 1 undo")


def main():
    test_build_undo("native")
    print("")
    test_build_undo("deformer")
    print("")
    test_delete_rig_undo()
    print("")
    test_reorder_undo()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
