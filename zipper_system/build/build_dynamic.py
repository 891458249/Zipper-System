# -*- coding: utf-8 -*-
"""Dynamic mechanic: attach a ddZipperDeformer per seam (ARCHITECTURE.md
sec.3.2 / sec.A).

Per seam we sample the two rails, bake the pair<->vertex correspondence, create
the deformer with membership limited to the seam vertices, wire the driver rails
(in world space) and drive ``zip`` from the seam controller.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya import cmds

from ..core.sampling import align_rails
from .corr import bake_correspondence

DEFORMER_TYPE = "ddZipperDeformer"


def _set_int_array(node_attr, values):
    cmds.setAttr(node_attr, len(values), *values, type="Int32Array")


def _ensure_zip_attr(controller):
    """Ensure the controller has a 0..1 'zip' attribute; return its plug."""
    if not cmds.attributeQuery("zip", node=controller, exists=True):
        cmds.addAttr(controller, longName="zip", attributeType="double",
                     min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    return "%s.zip" % controller


def build_seam_dynamic(target, seam, seam_index, rig_root=None,
                       target_kind="mesh"):
    """Build the dynamic deformer for one seam. Returns the deformer node name.

    target: the geometry to deform -- a mesh (target_kind='mesh') OR a NURBS
            curve (target_kind='curve'). The rails only drive it.
    seam:   core.seam.Seam (rail_a/rail_b expose world_plug / driver_vertex_ids).
    """
    n = seam.pair_count
    rail_a = seam.rail_a
    rail_b = seam.rail_b

    # -- sample + align (decide flipB) ------------------------------------- #
    da = rail_a.sample(n)
    db = rail_b.sample(n)
    pa = list(da.points)
    pb = list(db.points)
    aligned_b = align_rails(pa, pb)
    flip_b = aligned_b != pb
    pairs = list(zip(pa, aligned_b))

    # -- bake correspondence onto the target (mesh verts or curve CVs) ----- #
    corr_a, corr_b = bake_correspondence(target, pairs)
    members = sorted(set(corr_a) | set(corr_b))
    if not members:
        raise RuntimeError(
            "seam %d: no target components matched the rails" % seam_index)

    # -- create deformer with seam-only membership ------------------------- #
    comp_token = "cv" if target_kind == "curve" else "vtx"
    comps = ["%s.%s[%d]" % (target, comp_token, v) for v in members]
    cmds.select(comps, replace=True)
    node = cmds.deformer(type=DEFORMER_TYPE,
                         name="zipper_seam%d_DEF" % seam_index)[0]

    # -- params ------------------------------------------------------------ #
    cmds.setAttr("%s.pairCount" % node, n)
    cmds.setAttr("%s.feather" % node, seam.feather)
    dir_index = {"both": 0, "ltr": 1, "rtl": 2}.get(seam.direction, 0)
    cmds.setAttr("%s.direction" % node, dir_index)
    cmds.setAttr("%s.invertWipe" % node, bool(seam.invert))
    cmds.setAttr("%s.flipB" % node, bool(flip_b))

    _set_int_array("%s.corrA" % node, corr_a)
    _set_int_array("%s.corrB" % node, corr_b)
    _set_int_array("%s.railAVerts" % node, list(rail_a.driver_vertex_ids()))
    _set_int_array("%s.railBVerts" % node, list(rail_b.driver_vertex_ids()))

    # -- connect driver rails (world geometry) ----------------------------- #
    cmds.connectAttr(rail_a.world_plug(), "%s.railA" % node, force=True)
    cmds.connectAttr(rail_b.world_plug(), "%s.railB" % node, force=True)

    # -- drive zip from the controller ------------------------------------- #
    if seam.controller and cmds.objExists(seam.controller):
        zip_plug = _ensure_zip_attr(seam.controller)
        cmds.connectAttr(zip_plug, "%s.zip" % node, force=True)

    if rig_root and cmds.objExists(rig_root):
        # tag the deformer under the rig for bookkeeping (message connection)
        if not cmds.attributeQuery("zipperSeams", node=rig_root, exists=True):
            cmds.addAttr(rig_root, longName="zipperSeams", attributeType="message",
                         multi=True)
        idx = len(cmds.listConnections("%s.zipperSeams" % rig_root) or [])
        if not cmds.attributeQuery("zipperRig", node=node, exists=True):
            cmds.addAttr(node, longName="zipperRig", attributeType="message")
        cmds.connectAttr("%s.zipperSeams[%d]" % (rig_root, idx),
                         "%s.zipperRig" % node, force=True)

    return node
