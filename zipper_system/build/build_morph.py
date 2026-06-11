# -*- coding: utf-8 -*-
"""Morph mechanic: blendShape-driven static closer (ARCHITECTURE.md sec.B).

Per seam we drive a pre-sculpted "already closed" morph onto the final mesh
through a blendShape, and ramp its target weight from the seam controller via a
remapValue. Node count is O(1) per seam -> the GPU-friendly performance stand-in
for the dynamic deformer.

DESIGN NOTE (faithful to sec.B, with its tradeoff made explicit)
----------------------------------------------------------------
sec.B wants the wipe order baked as an along-seam gradient weight map. A single
blendShape target is a *linear multiply* (final = global * perVtxWeight), which
cannot reproduce the dynamic mechanic's per-pair *thresholded* sweep
clamp((z - t_k)/beta) AND still reach full closure at z = 1 (a 0..1 along-seam
ramp would leave the high-threshold end permanently open). So the morph build
provides a clean, fully-closing, controller-driven cross-fade localized to the
seam (the morph only differs from the base in the sculpted seam region, so the
effect is naturally local). For the exact corner->center wipe order, use the
dynamic mechanic. The controller curve shape is exposed through the remapValue
so artists can still ease the close.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya import cmds


def _ensure_zip_attr(controller):
    if not cmds.attributeQuery("zip", node=controller, exists=True):
        cmds.addAttr(controller, longName="zip", attributeType="double",
                     min=0.0, max=1.0, defaultValue=0.0, keyable=True)
    return "%s.zip" % controller


def build_seam_morph(final_mesh, morph_mesh, seam, seam_index, rig_root=None):
    """Build the blendShape closer for one seam. Returns the blendShape node."""
    bs = cmds.blendShape(
        morph_mesh, final_mesh, frontOfChain=True,
        name="zipper_seam%d_BS" % seam_index)[0]
    target_attr = "%s.weight[0]" % bs

    if seam.controller and cmds.objExists(seam.controller):
        zip_plug = _ensure_zip_attr(seam.controller)
        remap = cmds.createNode(
            "remapValue", name="zipper_seam%d_REMAP" % seam_index)
        cmds.connectAttr(zip_plug, "%s.inputValue" % remap, force=True)
        cmds.connectAttr("%s.outValue" % remap, target_attr, force=True)
        cmds.setAttr("%s.inputMin" % remap, 0.0)
        cmds.setAttr("%s.inputMax" % remap, 1.0)
        cmds.setAttr("%s.outputMin" % remap, 0.0)
        cmds.setAttr("%s.outputMax" % remap, 1.0)
        # feather shapes the ease of the close (0 = hard, 1 = very soft).
        beta = max(0.0, min(1.0, float(seam.feather)))
        # interp: 1=linear, 2=smooth. Soft feather -> smooth interpolation.
        cmds.setAttr("%s.value[0].value_Interp" % remap, 2 if beta > 0 else 1)
    else:
        cmds.setAttr(target_attr, 0.0)

    if rig_root and cmds.objExists(rig_root):
        if not cmds.attributeQuery("zipperSeams", node=rig_root, exists=True):
            cmds.addAttr(rig_root, longName="zipperSeams",
                         attributeType="message", multi=True)
        idx = len(cmds.listConnections("%s.zipperSeams" % rig_root) or [])
        if not cmds.attributeQuery("zipperRig", node=bs, exists=True):
            cmds.addAttr(bs, longName="zipperRig", attributeType="message")
        cmds.connectAttr("%s.zipperSeams[%d]" % (rig_root, idx),
                         "%s.zipperRig" % bs, force=True)

    return bs
