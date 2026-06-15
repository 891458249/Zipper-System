# -*- coding: utf-8 -*-
"""Curve zipper build: conform rail A & rail B onto the mid curve.

A seam is three NURBS curves: rail_a, mid, rail_b. As the controller's ``zip``
goes 0 -> 1, every CV of rail A and rail B is pulled onto the mid curve (the
seam line), reaching it exactly at zip = 1. Closing order is controlled by
direction / invert / feather.

Each rail gets its own ddZipperDeformer instance, driven by the mid curve. We
feed the SAME mid curve to both of the deformer's rail inputs, so its internal
midline m_k = 1/2 (mid_k + mid_k) = mid_k -- i.e. the rail conforms straight to
the mid curve. Every CV is a member (pairCount = CV count), so none is left
behind.
"""
from __future__ import absolute_import, division, print_function

from maya import cmds

from ..core.rail_curve import CurveRail
from ..core.math_util import vdist

DEFORMER_TYPE = "ddZipperDeformer"
_DIR_INDEX = {"both": 0, "ltr": 1, "rtl": 2}


def _set_int_array(node_attr, values):
    # cmds wants the list as a single argument for Int32Array.
    cmds.setAttr(node_attr, list(values), type="Int32Array")


def _ensure_zip_attr(controller):
    if not cmds.attributeQuery("zip", node=controller, exists=True):
        cmds.addAttr(controller, longName="zip", attributeType="double",
                     min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    return "%s.zip" % controller


def _align_component_ids(comp_pts, comp_ids, target_pts):
    """Return comp_ids, reversed if that better matches the target orientation,
    so ordered component i corresponds to target sample i."""
    if len(comp_pts) < 2 or len(target_pts) < 2:
        return list(comp_ids)
    c0, c1 = comp_pts[0], comp_pts[-1]
    f0, f1 = target_pts[0], target_pts[-1]
    same = vdist(f0, c0) + vdist(f1, c1)
    flipped = vdist(f0, c1) + vdist(f1, c0)
    return list(reversed(comp_ids)) if flipped < same else list(comp_ids)


def _tag_rig(node, rig_root):
    if not (rig_root and cmds.objExists(rig_root)):
        return
    if not cmds.attributeQuery("zipperSeams", node=rig_root, exists=True):
        cmds.addAttr(rig_root, longName="zipperSeams",
                     attributeType="message", multi=True)
    idx = len(cmds.listConnections("%s.zipperSeams" % rig_root) or [])
    if not cmds.attributeQuery("zipperRig", node=node, exists=True):
        cmds.addAttr(node, longName="zipperRig", attributeType="message")
    cmds.connectAttr("%s.zipperSeams[%d]" % (rig_root, idx),
                     "%s.zipperRig" % node, force=True)


def _conform_rail(rail, mid_rail, mid_plug, side, seam_index, params, rig_root):
    """Build one deformer that conforms *rail* onto the mid curve."""
    comp_pts, comp_ids, token = rail.component_world_points()
    m = len(comp_ids)
    if m < 2:
        raise RuntimeError(
            "seam %d rail %s: need at least 2 CVs" % (seam_index, side))

    # Every CV conforms: pairCount = CV count; sample mid to the same count so
    # ordered CV i lands on mid sample i (orientation-aligned).
    f_pts = list(mid_rail.sample(m).points)
    corr = _align_component_ids(comp_pts, comp_ids, f_pts)

    geo = rail.shape_name()
    comps = ["%s.%s[%d]" % (geo, token, v) for v in comp_ids]
    cmds.select(comps, replace=True)
    node = cmds.deformer(
        type=DEFORMER_TYPE,
        name="zipper_seam%d_%s_DEF" % (seam_index, side))[0]

    cmds.setAttr("%s.pairCount" % node, m)
    cmds.setAttr("%s.feather" % node, params["feather"])
    cmds.setAttr("%s.direction" % node,
                 _DIR_INDEX.get(params["direction"], 0))
    cmds.setAttr("%s.invertWipe" % node, bool(params["invert"]))
    cmds.setAttr("%s.flipB" % node, False)
    _set_int_array("%s.corrA" % node, corr)
    _set_int_array("%s.corrB" % node, [])
    _set_int_array("%s.railAVerts" % node, [])
    _set_int_array("%s.railBVerts" % node, [])
    cmds.connectAttr(mid_plug, "%s.railA" % node, force=True)
    cmds.connectAttr(mid_plug, "%s.railB" % node, force=True)

    controller = params.get("controller")
    if controller and cmds.objExists(controller):
        cmds.connectAttr(_ensure_zip_attr(controller),
                         "%s.zip" % node, force=True)
    _tag_rig(node, rig_root)
    return node


def build_seam(seam_spec, seam_index, rig_root=None):
    """Build one curve seam: conform rail_a and rail_b onto mid. Returns the
    created deformer node names."""
    rail_a = CurveRail.from_handle(seam_spec["rail_a"])
    rail_b = CurveRail.from_handle(seam_spec["rail_b"])
    mid = CurveRail.from_handle(seam_spec["mid"])

    # Defense in depth: shape_name() is the resolved full DAG path, so if mid is
    # the same curve as a rail (or the rails coincide) the conform would degrade
    # to a rail conforming onto itself. Refuse before any node is created; the
    # caller's transaction will undo() so no half-built rig is left behind.
    a_shape, b_shape, mid_shape = (
        rail_a.shape_name(), rail_b.shape_name(), mid.shape_name())
    if mid_shape in (a_shape, b_shape) or a_shape == b_shape:
        raise RuntimeError(
            "seam %d: mid/rail_a/rail_b resolve to the same curve, refusing "
            "to build" % seam_index)

    mid_plug = mid.world_plug()
    params = {
        "feather": float(seam_spec.get("feather", 0.15)),
        "direction": seam_spec.get("direction", "both"),
        "invert": bool(seam_spec.get("invert", False)),
        "controller": seam_spec.get("controller", ""),
    }
    return [
        _conform_rail(rail_a, mid, mid_plug, "A", seam_index, params, rig_root),
        _conform_rail(rail_b, mid, mid_plug, "B", seam_index, params, rig_root),
    ]
