# -*- coding: utf-8 -*-
"""Plugin-free native curve zipper build (ARCHITECTURE.md "Build modes").

Same result as the ddZipperDeformer build, but using ONLY stock Maya DG nodes,
so a rig built this way opens and animates downstream WITHOUT this plugin
installed (the deformer build is the compact alternative, gated behind a UI
opt-in). One mid + N rails; each rail's CVs conform onto the mid curve as the
controller's zip goes 0 -> 1.

Per CV a 4-node chain drives the rail's control point:

    mid.worldSpace[0] -> pointOnCurveInfo(.parameter=u_k).position    # live world target
    controller.<zip> -> remapValue(inputMin=lo_k, inputMax=hi_k).outValue   # wipe weight w_k
    blendColors(color1=poci.position, color2=restWorld_k, blender=w_k).output  # lerp rest<->mid
    pointMatrixMult(inPoint=blend.output, inMatrix=rail.worldInverseMatrix[0]).output -> railShape.controlPoints[cv]

The wipe ramp bounds (lo_k, hi_k) come from core.math_util.wipe_ramp_bounds,
which is the exact algebraic inverse of the deformer's wipe_weight, so both
build modes are visually identical. All helper DG nodes are message-tagged onto
rig_root.zipperNativeNodes[] so the rig deletes cleanly (see zipper_builder).
"""
from __future__ import absolute_import, division, print_function

from maya import cmds

from ..core.rail_curve import CurveRail
from ..core.math_util import wipe_ramp_bounds
# Reuse the single-sourced helpers so native and deformer builds stay in step.
from .build_dynamic import _align_component_ids, _ensure_zip_attr

NATIVE_NODES_ATTR = "zipperNativeNodes"


def _tag_native(node, rig_root):
    """Message-tag a helper DG node onto rig_root so cleanup can find it."""
    if not (rig_root and cmds.objExists(rig_root)):
        return
    if not cmds.attributeQuery(NATIVE_NODES_ATTR, node=rig_root, exists=True):
        cmds.addAttr(rig_root, longName=NATIVE_NODES_ATTR,
                     attributeType="message", multi=True)
    idx = len(cmds.listConnections(
        "%s.%s" % (rig_root, NATIVE_NODES_ATTR)) or [])
    cmds.connectAttr("%s.message" % node,
                     "%s.%s[%d]" % (rig_root, NATIVE_NODES_ATTR, idx),
                     force=True)


def _conform_rail_native(rail, mid_rail, mid_plug, side, seam_index, params,
                         zip_plug, rig_root):
    """Wire the native per-CV node chains conforming *rail* onto the mid curve."""
    # Native mode drives railShape.controlPoints[cv] with ABSOLUTE local coords.
    # controlPoints is absolute only on a history-free curve; with construction
    # history (e.g. a makeNurbCircle, common on real rig curves) it is a TWEAK
    # added on top of the .create input -- an absolute value would then double
    # (rest + rest), flinging the rail to ~2x rest so it looks like it vanished
    # and the zip slider seems dead (motion happens off-screen). Delete the
    # rail's history first to collapse it to history-free, making the existing
    # absolute connection correct; it's a no-op when there's no history. This
    # also gives zipper exclusive ownership of the rail shape, which native mode
    # requires. NEVER delete mid's history -- it is the read-only driver and may
    # carry its own animation/deformation. CV world positions are unchanged by
    # this, so the rest sampling below is unaffected.
    rail_xform = cmds.listRelatives(rail.shape_name(), parent=True,
                                    fullPath=True)
    if rail_xform:
        cmds.delete(rail_xform[0], constructionHistory=True)

    comp_pts, comp_ids, token = rail.component_world_points()
    m = len(comp_ids)
    if m < 2:
        raise RuntimeError(
            "seam %d rail %s: need at least 2 CVs" % (seam_index, side))

    # Mid sampled to m arc-length points; bind holds the curve param at each
    # (same sampling the deformer uses), so ordered CV k targets mid param u_k.
    mid_data = mid_rail.sample(m)
    f_pts = mid_data.points
    u_params = mid_data.bind
    corr = _align_component_ids(comp_pts, comp_ids, f_pts)

    shape = rail.shape_name()
    winv = "%s.worldInverseMatrix[0]" % shape
    beta = params["feather"]
    direction = params["direction"]
    invert = params["invert"]

    for k in range(m):
        cv_id = corr[k]
        rest = comp_pts[cv_id]
        u_k = u_params[k]
        lo, hi = wipe_ramp_bounds(k, m, beta, direction, invert)
        base = "zs%dr%s_c%d" % (seam_index, side, cv_id)

        poci = cmds.createNode("pointOnCurveInfo", name=base + "_poci")
        cmds.connectAttr(mid_plug, "%s.inputCurve" % poci, force=True)
        cmds.setAttr("%s.turnOnPercentage" % poci, 0)
        cmds.setAttr("%s.parameter" % poci, u_k)

        remap = cmds.createNode("remapValue", name=base + "_remap")
        cmds.setAttr("%s.inputMin" % remap, lo)
        cmds.setAttr("%s.inputMax" % remap, hi)
        if zip_plug:
            cmds.connectAttr(zip_plug, "%s.inputValue" % remap, force=True)

        blend = cmds.createNode("blendColors", name=base + "_blend")
        cmds.connectAttr("%s.position" % poci, "%s.color1" % blend, force=True)
        cmds.setAttr("%s.color2" % blend, rest[0], rest[1], rest[2],
                     type="double3")
        cmds.connectAttr("%s.outValue" % remap, "%s.blender" % blend,
                         force=True)

        pmm = cmds.createNode("pointMatrixMult", name=base + "_pmm")
        cmds.connectAttr("%s.output" % blend, "%s.inPoint" % pmm, force=True)
        cmds.connectAttr(winv, "%s.inMatrix" % pmm, force=True)
        cmds.connectAttr("%s.output" % pmm,
                         "%s.controlPoints[%d]" % (shape, cv_id), force=True)

        for n in (poci, remap, blend, pmm):
            _tag_native(n, rig_root)


def build_seam(seam_spec, seam_index, rig_root=None):
    """Build one curve seam with stock DG nodes only (no plugin). Returns []
    (the native build creates DG helper nodes, not deformer nodes)."""
    mid = CurveRail.from_handle(seam_spec["mid"])
    rails = [CurveRail.from_handle(h) for h in seam_spec["rails"]]

    # Defense in depth (mirrors build_dynamic): reject mid == any rail before
    # creating anything; the caller's transaction undo()s on raise.
    mid_shape = mid.shape_name()
    for j, rail in enumerate(rails):
        if rail.shape_name() == mid_shape:
            raise RuntimeError(
                "seam %d: rail %d and mid resolve to the same curve, refusing "
                "to build" % (seam_index, j))

    mid_plug = mid.world_plug()
    params = {
        "feather": float(seam_spec.get("feather", 0.15)),
        "direction": seam_spec.get("direction", "both"),
        "invert": bool(seam_spec.get("invert", False)),
        "controller": seam_spec.get("controller", ""),
        "zip_attr": (seam_spec.get("zip_attr") or "zip"),
    }
    controller = params["controller"]
    zip_plug = None
    if controller and cmds.objExists(controller):
        zip_plug = _ensure_zip_attr(controller, params["zip_attr"])

    for j, rail in enumerate(rails):
        _conform_rail_native(rail, mid, mid_plug, "%d" % j, seam_index, params,
                             zip_plug, rig_root)
    return []
