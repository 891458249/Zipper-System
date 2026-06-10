# -*- coding: utf-8 -*-
"""Manual Maya smoke test for the Zipper System (run in the Script Editor).

NOT a pytest test -- it requires a running Maya. Paste the whole file into a
Python tab of the Maya Script Editor (with the repo root on sys.path) and run.

It builds a tiny rig and tells you what to look for. Two scenarios:

    smoke_dynamic()  -> ddZipperDeformer driven by curve rails
    smoke_morph()    -> blendShape closer driven by a controller

Expected results are printed and described inline.
"""

import sys

# --- make the package importable (edit to your checkout path if needed) ----- #
# e.g. sys.path.append(r"X:/Plugins/Zipper System")

from maya import cmds


def _fresh_scene():
    cmds.file(new=True, force=True)


def _make_strip_and_rails():
    """A 1-row poly strip plus two curves along its long edges."""
    # head_GEO: 20 x 2 plane, 10 wide, 2 tall, centered at origin.
    plane = cmds.polyPlane(
        name="head_GEO", width=10, height=2,
        subdivisionsX=20, subdivisionsY=1)[0]
    # top edge (y = +1) and bottom edge (y = -1) rows of verts -> rails
    top_pts = [(-5 + i * (10.0 / 20), 1.0, 0.0) for i in range(21)]
    bot_pts = [(-5 + i * (10.0 / 20), -1.0, 0.0) for i in range(21)]
    rail_a = cmds.curve(name="rail_top_CRV", degree=1, point=top_pts)
    rail_b = cmds.curve(name="rail_bot_CRV", degree=1, point=bot_pts)
    ctrl = cmds.spaceLocator(name="jaw_zip_CTRL")[0]
    return plane, rail_a, rail_b, ctrl


def smoke_dynamic():
    from zipper_system.build import zipper_builder
    _fresh_scene()
    plane, rail_a, rail_b, ctrl = _make_strip_and_rails()

    rig_spec = {
        "name": "smokeDyn",
        "final_mesh": plane,
        "mechanic": "dynamic",
        "seams": [{
            "rail_a": {"type": "curve", "handle": rail_a},
            "rail_b": {"type": "curve", "handle": rail_b},
            "pair_count": 21,
            "feather": 0.2,
            "direction": "both",
            "controller": ctrl,
        }],
    }
    root = zipper_builder.build(rig_spec)
    defs = cmds.ls(type="ddZipperDeformer")
    print("[dynamic] rig root:", root)
    print("[dynamic] deformer nodes:", defs)
    print("[dynamic] EXPECTED: exactly one 'ddZipperDeformer', root group exists.")
    print("[dynamic] NOW scrub %s.zip from 0 -> 1:" % ctrl)
    print("          - at zip=0 the strip is flat (open).")
    print("          - as zip rises the CORNERS (x=+-5) seal to y=0 FIRST,")
    print("            the center seals LAST (ends -> center, the sec.3.3 fix).")
    print("          - set %s.invertWipe 1 to flip to center -> ends." % defs[0])
    cmds.setAttr("%s.zip" % ctrl, 0.6)
    print("[dynamic] set zip=0.6; inspect the viewport.")
    return root


def smoke_morph():
    from zipper_system.build import zipper_builder
    _fresh_scene()
    plane, rail_a, rail_b, ctrl = _make_strip_and_rails()

    # morph target: a copy with the two rows collapsed to the midline (closed).
    morph = cmds.duplicate(plane, name="head_closed_GEO")[0]
    n = cmds.polyEvaluate(morph, vertex=True)
    for v in range(n):
        p = cmds.pointPosition("%s.vtx[%d]" % (morph, v), world=True)
        cmds.move(p[0], 0.0, p[2], "%s.vtx[%d]" % (morph, v), absolute=True)

    rig_spec = {
        "name": "smokeMorph",
        "final_mesh": plane,
        "mechanic": "morph",
        "morph_mesh": morph,
        "seams": [{
            "rail_a": {"type": "curve", "handle": rail_a},
            "rail_b": {"type": "curve", "handle": rail_b},
            "pair_count": 21,
            "feather": 0.2,
            "direction": "both",
            "controller": ctrl,
        }],
    }
    root = zipper_builder.build(rig_spec)
    bs = cmds.ls(type="blendShape")
    print("[morph] rig root:", root)
    print("[morph] blendShape nodes:", bs)
    print("[morph] EXPECTED: one blendShape + one remapValue; root group exists.")
    print("[morph] scrub %s.zip 0 -> 1: strip cross-fades flat -> fully closed."
          % ctrl)
    cmds.setAttr("%s.zip" % ctrl, 1.0)
    print("[morph] set zip=1.0; strip should be fully sealed to y=0.")
    return root


def smoke_validation():
    """Invalid spec must raise BEFORE any node is created (sec.8)."""
    from zipper_system.build import zipper_builder
    from zipper_system.build.zipper_builder import ZipperValidationError
    _fresh_scene()
    before = set(cmds.ls())
    bad = {
        "name": "bad", "final_mesh": "does_not_exist", "mechanic": "dynamic",
        "seams": [{"rail_a": {"type": "curve", "handle": "nope"},
                   "rail_b": {"type": "curve", "handle": "nope"},
                   "pair_count": 5, "controller": ""}],
    }
    try:
        zipper_builder.build(bad)
        print("[validate] ERROR: build should have raised!")
    except ZipperValidationError as exc:
        after = set(cmds.ls())
        leaked = after - before
        print("[validate] raised as expected:\n", exc)
        print("[validate] nodes leaked (must be empty set):", leaked)


if __name__ == "__main__":
    smoke_dynamic()
    # smoke_morph()
    # smoke_validation()
