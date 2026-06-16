# -*- coding: utf-8 -*-
"""Standalone proof of the rig traceability / Manage features (headless).

Run (no GUI):
    mayapy verify_rig_manager.py        # Py3 (Maya 2023+)
    mayapy2 verify_rig_manager.py       # Py2.7 (Maya 2022)

Covers (ARCHITECTURE.md "Rig traceability & management"):
  1. Build a native rig (2 seams) and a deformer rig (1 seam); ZipperAction
     .list_rigs() returns BOTH with correct name / mode / seams / controllers /
     #nodes.
  2. Legacy fallback: strip the discoverable stamp from a rig, leaving only its
     zipperNativeNodes array; list_rigs() still lists it (best-effort metadata).
  3. Selective delete: delete one rig -> list drops to 1, the other rig is
     intact, and the deleted rig's USER input curves / controller survive.
  4. select_rig(): selection == rig_root + the nodes the rig created, and never
     the user's input curves.

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

from zipper_system.build import zipper_builder            # noqa: E402
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


def _by_name(rigs, name):
    for r in rigs:
        if r["name"] == name:
            return r
    return None


def _build_native_2seams():
    mid0 = _line("nMid0", 0.0, 0.0)
    a0 = _line("nA0", 0.0, 2.0)
    b0 = _line("nB0", 0.0, -2.0)
    mid1 = _line("nMid1", 10.0, 0.0)
    a1 = _line("nA1", 10.0, 2.0)
    b1 = _line("nB1", 10.0, -2.0)
    ctrl = cmds.spaceLocator(name="nCTRL")[0]
    return zipper_builder.build({
        "name": "rigA_native", "build_mode": "native",
        "seams": [
            {"mid": mid0, "rails": [a0, b0], "feather": 0.15,
             "direction": "both", "invert": False, "controller": ctrl},
            {"mid": mid1, "rails": [a1, b1], "feather": 0.15,
             "direction": "both", "invert": False, "controller": ctrl},
        ]})


def _build_deformer_1seam():
    mid = _line("dMid", 20.0, 0.0)
    a = _line("dA", 20.0, 2.0)
    b = _line("dB", 20.0, -2.0)
    ctrl = cmds.spaceLocator(name="dCTRL")[0]
    return zipper_builder.build({
        "name": "rigB_deformer", "build_mode": "deformer",
        "seams": [{"mid": mid, "rails": [a, b], "feather": 0.15,
                   "direction": "both", "invert": False, "controller": ctrl}]})


def test_list_two_rigs():
    cmds.file(new=True, force=True)
    _build_native_2seams()
    _build_deformer_1seam()

    rigs = ZipperAction.list_rigs()
    check(len(rigs) == 2, "list_rigs() returns 2 rigs (got %d)" % len(rigs))

    nat = _by_name(rigs, "rigA_native")
    deformer = _by_name(rigs, "rigB_deformer")
    check(nat is not None, "native rig listed by name")
    check(deformer is not None, "deformer rig listed by name")

    if nat:
        check(nat["mode"] == "native", "native rig mode == 'native'")
        check(nat["seams"] == 2, "native rig seam count == 2 (got %r)"
              % nat["seams"])
        check(nat["controllers"] == "nCTRL",
              "native rig controllers == 'nCTRL' (got %r)" % nat["controllers"])
        check(nat["nodes"] > 0, "native rig reports created nodes (%d)"
              % nat["nodes"])
    if deformer:
        check(deformer["mode"] == "deformer", "deformer rig mode == 'deformer'")
        check(deformer["seams"] == 1, "deformer rig seam count == 1 (got %r)"
              % deformer["seams"])
        check(deformer["controllers"] == "dCTRL",
              "deformer rig controllers == 'dCTRL' (got %r)"
              % deformer["controllers"])
        check(deformer["nodes"] > 0, "deformer rig reports created nodes (%d)"
              % deformer["nodes"])


def test_legacy_fallback():
    cmds.file(new=True, force=True)
    root = _build_native_2seams()
    # Strip the discoverable stamp, leaving only zipperNativeNodes (an old rig).
    for attr in (zipper_builder.RIG_ROOT_ATTR, zipper_builder.RIG_NAME_ATTR,
                 zipper_builder.RIG_MODE_ATTR, zipper_builder.RIG_SEAMCOUNT_ATTR,
                 zipper_builder.RIG_CONTROLLERS_ATTR):
        if cmds.attributeQuery(attr, node=root, exists=True):
            cmds.deleteAttr("%s.%s" % (root, attr))

    rigs = ZipperAction.list_rigs()
    check(len(rigs) == 1, "legacy rig still listed (got %d)" % len(rigs))
    if rigs:
        r = rigs[0]
        check(r["name"] == "rigA_native",
              "legacy name inferred from node ('%s')" % r["name"])
        check(r["mode"] == "?", "legacy mode is unknown '?'")
        check(r["nodes"] > 0, "legacy rig still reports created nodes (%d)"
              % r["nodes"])


def test_selective_delete():
    cmds.file(new=True, force=True)
    nat = _build_native_2seams()
    _build_deformer_1seam()
    check(len(ZipperAction.list_rigs()) == 2, "two rigs before delete")

    # The native rig's USER assets (must survive a delete).
    user_curves = ["nMid0", "nA0", "nB0", "nMid1", "nA1", "nB1", "nCTRL"]

    ZipperAction.delete_rig(nat)
    rigs = ZipperAction.list_rigs()
    check(len(rigs) == 1, "list drops to 1 after deleting one rig (got %d)"
          % len(rigs))
    check(_by_name(rigs, "rigB_deformer") is not None,
          "the other rig is intact after delete")
    survived = [c for c in user_curves if cmds.objExists(c)]
    check(len(survived) == len(user_curves),
          "deleted rig's input curves/controller survive (%d/%d)"
          % (len(survived), len(user_curves)))
    check(not cmds.objExists(nat), "deleted rig_root is gone")


def test_select_rig():
    cmds.file(new=True, force=True)
    root = _build_native_2seams()
    sel = set(cmds.ls(ZipperAction.select_rig(root), long=True) or [])

    root_full = cmds.ls(root, long=True)[0]
    check(root_full in sel, "selection contains the rig_root")

    created = set(cmds.ls(ZipperAction._created_nodes(root), long=True) or [])
    check(created and created.issubset(sel),
          "selection contains every created node")

    # User input curves must NOT be in the trace selection.
    inputs = []
    for c in ("nMid0", "nA0", "nB0", "nCTRL"):
        inputs.extend(cmds.ls(c, long=True) or [])
    leaked = [c for c in inputs if c in sel]
    check(not leaked, "selection excludes user input curves/controller")


def main():
    test_list_two_rigs()
    print("")
    test_legacy_fallback()
    print("")
    test_selective_delete()
    print("")
    test_select_rig()
    print("")
    if _FAILURES:
        print("==== %d FAILURE(S) ====" % len(_FAILURES))
        for f in _FAILURES:
            print("  - " + f)
        sys.exit(1)
    print("==== ALL CHECKS PASSED ====")


if __name__ == "__main__":
    main()
