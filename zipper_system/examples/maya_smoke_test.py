# -*- coding: utf-8 -*-
"""Manual Maya smoke test for the Zipper System (curve-only).

NOT a pytest test -- it requires a running Maya. Paste into a Python tab of the
Maya Script Editor (with the repo root on sys.path) and run ``smoke()``.

It builds a tiny three-curve seam (Rail A, Mid Curve, Rail B) and tells you what
to look for.
"""
from __future__ import absolute_import, division, print_function

import sys  # noqa: F401  (edit sys.path to your checkout if needed)

from maya import cmds


def smoke():
    from zipper_system.build import zipper_builder
    cmds.file(new=True, force=True)

    # Rail A above, Rail B below, Mid Curve between them.
    rail_a = cmds.curve(name="railA_CRV", degree=3,
                        point=[(i, 1.0, 0) for i in range(8)])
    rail_b = cmds.curve(name="railB_CRV", degree=3,
                        point=[(i, -1.0, 0) for i in range(8)])
    mid = cmds.curve(name="mid_CRV", degree=3,
                     point=[(i, 0.0, 0) for i in range(8)])
    ctrl = cmds.spaceLocator(name="zip_CTRL")[0]

    rig_spec = {
        "name": "smokeZip",
        "seams": [{
            "mid": mid,
            "rails": [rail_a, rail_b],
            "feather": 0.2,
            "direction": "both",
            "invert": False,
            "controller": ctrl,
        }],
    }
    root = zipper_builder.build(rig_spec)
    print("[smoke] rig root:", root)
    print("[smoke] deformers:", cmds.ls(type="ddZipperDeformer"))
    print("[smoke] EXPECTED: two deformers (railA / railB), one rig group.")
    print("[smoke] NOW scrub %s.zip 0 -> 1:" % ctrl)
    print("        - zip=0: railA at y=+1, railB at y=-1 (open).")
    print("        - rising: the ENDS seal onto the mid curve first, the")
    print("          centre last (ends -> centre; set invertWipe for the")
    print("          opposite).")
    print("        - zip=1: BOTH rails lie exactly on the mid curve (y=0).")
    cmds.setAttr("%s.zip" % ctrl, 1.0)
    print("[smoke] set zip=1; both rails should sit on the mid curve.")
    return root


def smoke_validation():
    """Invalid spec must raise BEFORE creating anything."""
    from zipper_system.build import zipper_builder
    from zipper_system.build.zipper_builder import ZipperValidationError
    cmds.file(new=True, force=True)
    before = set(cmds.ls())
    bad = {"name": "bad", "seams": [
        {"mid": "nope", "rails": ["nope", "nope"],
         "direction": "both", "controller": ""}]}
    try:
        zipper_builder.build(bad)
        print("[validate] ERROR: should have raised!")
    except ZipperValidationError as exc:
        leaked = set(cmds.ls()) - before
        print("[validate] raised as expected:\n", exc)
        print("[validate] nodes leaked (must be empty):", leaked)


if __name__ == "__main__":
    smoke()
    # smoke_validation()
