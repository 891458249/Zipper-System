# -*- coding: utf-8 -*-
"""Dynamic mechanic: attach a ddZipperDeformer per seam (ARCHITECTURE.md
sec.3.2 / sec.A).

Two rig types, chosen by the deform target:

* MESH target (mesh mode): deform the picked mesh toward the rails' live midline
  (the rails drive the mesh -- original sticky-lips-to-centre behaviour).

* CURVE target (curve mode / conform): deform rail A and rail B THEMSELVES onto
  the final curve. The final curve is the driver/seam line; at zip = 1 the rails
  conform to it exactly. The rails may be curves (deform CVs) or edges (deform
  the mesh's edge vertices). Implemented by feeding the SAME final curve to both
  rail inputs of the deformer, so its midline collapses to the curve point, and
  applying one deformer instance per rail.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya import cmds

from ..core.sampling import align_rails
from ..core.rail_curve import CurveRail
from .corr import bake_correspondence

DEFORMER_TYPE = "ddZipperDeformer"


def _set_int_array(node_attr, values):
    # cmds wants the list passed as a single argument for Int32Array; the
    # MEL-style "count, *values" form raises "Too much data was provided".
    cmds.setAttr(node_attr, list(values), type="Int32Array")


def _ensure_zip_attr(controller):
    """Ensure the controller has a 0..1 'zip' attribute; return its plug."""
    if not cmds.attributeQuery("zip", node=controller, exists=True):
        cmds.addAttr(controller, longName="zip", attributeType="double",
                     min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    return "%s.zip" % controller


def _align_component_ids(comp_pts, comp_ids, target_pts):
    """Return comp_ids, reversed if that better matches the target's orientation,
    so ordered component i corresponds to target sample i (and conforms to it)."""
    from ..core.math_util import vdist
    if len(comp_pts) < 2 or len(target_pts) < 2:
        return list(comp_ids)
    c0, c1 = comp_pts[0], comp_pts[-1]
    f0, f1 = target_pts[0], target_pts[-1]
    same = vdist(f0, c0) + vdist(f1, c1)
    flipped = vdist(f0, c1) + vdist(f1, c0)
    if flipped < same:
        return list(reversed(comp_ids))
    return list(comp_ids)


def _set_common_params(node, seam):
    cmds.setAttr("%s.pairCount" % node, seam.pair_count)
    cmds.setAttr("%s.feather" % node, seam.feather)
    dir_index = {"both": 0, "ltr": 1, "rtl": 2}.get(seam.direction, 0)
    cmds.setAttr("%s.direction" % node, dir_index)
    cmds.setAttr("%s.invertWipe" % node, bool(seam.invert))


def _drive_zip(node, seam):
    if seam.controller and cmds.objExists(seam.controller):
        cmds.connectAttr(_ensure_zip_attr(seam.controller),
                         "%s.zip" % node, force=True)


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


# --------------------------------------------------------------------------- #
# dispatcher
# --------------------------------------------------------------------------- #
def build_seam_dynamic(target, seam, seam_index, rig_root=None,
                       target_kind="mesh"):
    """Build the dynamic deformer(s) for one seam.

    target_kind='curve' -> conform: rail A & rail B deform onto `target` curve.
    target_kind='mesh'  -> midline: `target` mesh deforms toward the rails.
    Returns the created deformer node name(s).
    """
    if target_kind == "curve":
        return _build_conform(target, seam, seam_index, rig_root)
    return _build_midline(target, seam, seam_index, rig_root)


# --------------------------------------------------------------------------- #
# mesh mode: deform the target mesh toward the rails' midline (original)
# --------------------------------------------------------------------------- #
def _build_midline(target, seam, seam_index, rig_root):
    n = seam.pair_count
    rail_a, rail_b = seam.rail_a, seam.rail_b

    da = rail_a.sample(n)
    db = rail_b.sample(n)
    pa = list(da.points)
    pb = list(db.points)
    aligned_b = align_rails(pa, pb)
    flip_b = aligned_b != pb
    pairs = list(zip(pa, aligned_b))

    corr_a, corr_b = bake_correspondence(target, pairs)
    members = sorted(set(corr_a) | set(corr_b))
    if not members:
        raise RuntimeError(
            "seam %d: no target components matched the rails" % seam_index)

    comps = ["%s.vtx[%d]" % (target, v) for v in members]
    cmds.select(comps, replace=True)
    node = cmds.deformer(type=DEFORMER_TYPE,
                         name="zipper_seam%d_DEF" % seam_index)[0]

    _set_common_params(node, seam)
    cmds.setAttr("%s.flipB" % node, bool(flip_b))
    _set_int_array("%s.corrA" % node, corr_a)
    _set_int_array("%s.corrB" % node, corr_b)
    _set_int_array("%s.railAVerts" % node, list(rail_a.driver_vertex_ids()))
    _set_int_array("%s.railBVerts" % node, list(rail_b.driver_vertex_ids()))
    cmds.connectAttr(rail_a.world_plug(), "%s.railA" % node, force=True)
    cmds.connectAttr(rail_b.world_plug(), "%s.railB" % node, force=True)
    _drive_zip(node, seam)
    _tag_rig(node, rig_root)
    return node


# --------------------------------------------------------------------------- #
# curve mode: deform rail A & rail B onto the final curve (conform)
# --------------------------------------------------------------------------- #
def _build_conform(target_curve, seam, seam_index, rig_root):
    tgt_rail = CurveRail.from_handle(target_curve)
    tgt_plug = tgt_rail.world_plug()

    nodes = []
    for side, rail in (("A", seam.rail_a), ("B", seam.rail_b)):
        comp_pts, comp_ids, token = rail.component_world_points()
        m = len(comp_ids)
        if m < 2:
            raise RuntimeError(
                "seam %d rail %s: need at least 2 components" % (seam_index, side))

        # EVERY component conforms: pairCount = component count, and the target
        # is sampled to the same count, so component i lands on target sample i.
        # (A smaller pair_count would leave the extra components behind.)
        f_pts = list(tgt_rail.sample(m).points)
        corr = _align_component_ids(comp_pts, comp_ids, f_pts)

        geo = rail.shape_name()
        comps = ["%s.%s[%d]" % (geo, token, v) for v in comp_ids]
        cmds.select(comps, replace=True)
        node = cmds.deformer(
            type=DEFORMER_TYPE,
            name="zipper_seam%d_%s_DEF" % (seam_index, side))[0]

        cmds.setAttr("%s.pairCount" % node, m)
        cmds.setAttr("%s.feather" % node, seam.feather)
        cmds.setAttr("%s.direction" % node,
                     {"both": 0, "ltr": 1, "rtl": 2}.get(seam.direction, 0))
        cmds.setAttr("%s.invertWipe" % node, bool(seam.invert))
        cmds.setAttr("%s.flipB" % node, False)
        _set_int_array("%s.corrA" % node, corr)
        _set_int_array("%s.corrB" % node, [])
        _set_int_array("%s.railAVerts" % node, [])
        _set_int_array("%s.railBVerts" % node, [])
        # Feed the SAME final curve to both rail inputs -> the deformer's
        # midline m_k = 1/2 (f_k + f_k) = f_k, so members conform to the curve.
        cmds.connectAttr(tgt_plug, "%s.railA" % node, force=True)
        cmds.connectAttr(tgt_plug, "%s.railB" % node, force=True)
        _drive_zip(node, seam)
        _tag_rig(node, rig_root)
        nodes.append(node)
    return nodes
