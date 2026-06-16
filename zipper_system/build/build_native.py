# -*- coding: utf-8 -*-
"""Plugin-free native curve zipper build (ARCHITECTURE.md "Build modes").

Same result as the ddZipperDeformer build, but using ONLY stock Maya DG nodes,
so a rig built this way opens and animates downstream WITHOUT this plugin
installed (the deformer build is the compact alternative, gated behind a UI
opt-in). One mid + N rails; each rail's CVs conform onto the mid curve as the
controller's zip goes 0 -> 1.

Per CV a node chain drives the rail's control point:

    mid.worldSpace[0]    -> pointOnCurveInfo(.parameter=u_k).position    # live target
    driver.worldSpace[0] -> pointOnCurveInfo(.parameter=u_cv).position   # live rest
    controller.<zip>     -> remapValue(inputMin=lo_k, inputMax=hi_k).outValue   # wipe w_k
    blendColors(color1=midPoci, color2=driverPoci, blender=w_k).output   # lerp rest<->mid
    pointMatrixMult(inPoint=blend.output, inMatrix=rail.worldInverseMatrix[0]).output
        -> railShape.controlPoints[cv]

The rest comes from a hidden DRIVER duplicate of the rail rather than a baked
constant: if the rail is skinned, the skin is migrated to the driver so the rest
follows the bones, letting a plugin-free rig compose with skinCluster (output
rail = driver at zip=0, = mid at zip=1; the output itself carries no skin).

The wipe ramp bounds (lo_k, hi_k) come from core.math_util.wipe_ramp_bounds,
the exact algebraic inverse of the deformer's wipe_weight, so both build modes
are visually identical. All helper DG nodes AND the driver curve are message-
tagged onto rig_root.zipperNativeNodes[] so the rig deletes cleanly (see
zipper_builder.delete_rig).
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


def _find_skin(shape):
    """Return the skinCluster deforming *shape*, or None."""
    for n in cmds.listHistory(shape, pruneDagObjects=True) or []:
        if cmds.nodeType(n) == "skinCluster":
            return n
    return None


def _build_driver(rail, side, seam_index, rig_root):
    """Create the hidden DRIVER duplicate that carries this rail's live rest.

    If the rail is skinned, the skin is migrated onto the driver (re-bind to the
    same influences + copySkinWeights) so the driver follows the bones in real
    time. If not, the driver is a static duplicate (== the old static rest;
    skinning the driver later just works). Returns the driver's worldSpace plug.
    """
    rail_shape = rail.shape_name()
    rail_xform = cmds.listRelatives(rail_shape, parent=True, fullPath=True)[0]
    skin = _find_skin(rail_shape)

    dup = cmds.duplicate(rail_xform, returnRootsOnly=True,
                         name="zs%dr%s_zipDriver" % (seam_index, side))[0]
    dup = cmds.ls(dup, long=True)[0]
    # duplicate doesn't copy the upstream skin; strip any tweak/history so the
    # driver is a clean curve at bind pose, then give it its own skin.
    cmds.delete(dup, constructionHistory=True)
    driver_shape = cmds.listRelatives(dup, shapes=True, fullPath=True,
                                      noIntermediate=True)[0]

    if skin:
        infs = cmds.skinCluster(skin, query=True, influence=True) or []
        if infs:
            driver_skin = cmds.skinCluster(
                infs, dup, toSelectedBones=True, removeUnusedInfluence=False,
                name="zs%dr%s_driverSkin" % (seam_index, side))[0]
            cmds.copySkinWeights(
                sourceSkin=skin, destinationSkin=driver_skin, noMirror=True,
                surfaceAssociation="closestPoint",
                influenceAssociation=["closestJoint", "oneToOne"])

    cmds.setAttr("%s.visibility" % dup, False)
    _tag_native(dup, rig_root)
    return "%s.worldSpace[0]" % driver_shape


def _conform_rail_native(rail, mid_rail, mid_plug, side, seam_index, params,
                         zip_plug, rig_root):
    """Wire the native per-CV node chains conforming *rail* onto the mid curve.

    Rest comes from a hidden DRIVER duplicate (carrying the rail's skin if any),
    sampled live per CV, so the rig composes with skinCluster: zip=0 -> output =
    driver (follows bones), zip=1 -> output = mid. The output rail itself carries
    no skin/history -- it is driven purely by this network, so its controlPoints
    can be set absolutely (see the history note below)."""
    # Build the driver BEFORE stripping the output: it captures the rail's skin
    # while it is still live.
    driver_plug = _build_driver(rail, side, seam_index, rig_root)

    # Output rail must be history-free so controlPoints drives ABSOLUTELY (on a
    # history-bearing curve controlPoints is an additive tweak -> rest would
    # double). This also removes the rail's own skinCluster -- the skin now lives
    # on the driver. NEVER touch mid's history (read-only driver curve).
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
    # cv_params gives each output CV's own curve param for the driver (rest).
    mid_data = mid_rail.sample(m)
    f_pts = mid_data.points
    u_params = mid_data.bind
    corr = _align_component_ids(comp_pts, comp_ids, f_pts)
    cv_params = rail.cv_params()

    shape = rail.shape_name()
    winv = "%s.worldInverseMatrix[0]" % shape
    beta = params["feather"]
    direction = params["direction"]
    invert = params["invert"]

    for k in range(m):
        cv_id = corr[k]
        u_mid = u_params[k]
        u_drv = cv_params[cv_id]
        lo, hi = wipe_ramp_bounds(k, m, beta, direction, invert)
        base = "zs%dr%s_c%d" % (seam_index, side, cv_id)

        mid_poci = cmds.createNode("pointOnCurveInfo", name=base + "_midPoci")
        cmds.connectAttr(mid_plug, "%s.inputCurve" % mid_poci, force=True)
        cmds.setAttr("%s.turnOnPercentage" % mid_poci, 0)
        cmds.setAttr("%s.parameter" % mid_poci, u_mid)

        # Live rest: the driver's point at this CV's own param (follows skin).
        drv_poci = cmds.createNode("pointOnCurveInfo", name=base + "_drvPoci")
        cmds.connectAttr(driver_plug, "%s.inputCurve" % drv_poci, force=True)
        cmds.setAttr("%s.turnOnPercentage" % drv_poci, 0)
        cmds.setAttr("%s.parameter" % drv_poci, u_drv)

        remap = cmds.createNode("remapValue", name=base + "_remap")
        cmds.setAttr("%s.inputMin" % remap, lo)
        cmds.setAttr("%s.inputMax" % remap, hi)
        if zip_plug:
            cmds.connectAttr(zip_plug, "%s.inputValue" % remap, force=True)

        blend = cmds.createNode("blendColors", name=base + "_blend")
        cmds.connectAttr("%s.position" % mid_poci, "%s.color1" % blend,
                         force=True)
        cmds.connectAttr("%s.position" % drv_poci, "%s.color2" % blend,
                         force=True)
        cmds.connectAttr("%s.outValue" % remap, "%s.blender" % blend,
                         force=True)

        pmm = cmds.createNode("pointMatrixMult", name=base + "_pmm")
        cmds.connectAttr("%s.output" % blend, "%s.inPoint" % pmm, force=True)
        cmds.connectAttr(winv, "%s.inMatrix" % pmm, force=True)
        cmds.connectAttr("%s.output" % pmm,
                         "%s.controlPoints[%d]" % (shape, cv_id), force=True)

        for n in (mid_poci, drv_poci, remap, blend, pmm):
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
