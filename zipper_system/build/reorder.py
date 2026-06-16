# -*- coding: utf-8 -*-
"""Keep zipper deformers at the END of their rail deformation chains.

The zipper deformer must be the LAST deformer on each rail (downstream of skin):
otherwise an already-closed CV is still re-displaced by the rail's own
skinCluster, double-counting the bone transform. ``cmds.deformer`` appends at the
chain end, so building the zipper AFTER skinning is already correct. This module
fixes the reverse workflow (skin added AFTER the zipper was built) on demand:
``reorder_rig_to_chain_end`` walks every zipper deformer in a rig and pushes it
behind all other deformers on its rail.
"""
from __future__ import absolute_import, division, print_function

from maya import cmds

DEFORMER_TYPE = "ddZipperDeformer"
_SEAMS_ATTR = "zipperSeams"


def _is_deformer(node):
    return "geometryFilter" in (cmds.nodeType(node, inherited=True) or [])


def _chain_deformers(geo):
    """All deformers acting on geometry *geo* (dedup, in history order)."""
    out = []
    for n in cmds.listHistory(geo, pruneDagObjects=True) or []:
        if _is_deformer(n) and n not in out:
            out.append(n)
    return out


def reorder_zipper_to_end(zipper_def):
    """Make *zipper_def* the last deformer on each geometry it drives."""
    for geo in cmds.deformer(zipper_def, query=True, geometry=True) or []:
        for d in _chain_deformers(geo):
            if d == zipper_def:
                continue
            # reorderDeformers(A, B, geo) places A downstream of (applied AFTER)
            # B, so (zipper, other) pushes the zipper past each other deformer
            # -> zipper ends up last.
            try:
                cmds.reorderDeformers(zipper_def, d, geo)
            except RuntimeError:
                pass


def reorder_rig_to_chain_end(rig_root):
    """Reorder every zipper deformer of a built rig to its rail's chain end.

    No-op for native rigs (they have no zipper deformer nodes). Returns the list
    of deformers it reordered.
    """
    if not (rig_root and cmds.objExists(rig_root)):
        return []
    if not cmds.attributeQuery(_SEAMS_ATTR, node=rig_root, exists=True):
        return []
    done = []
    for d in cmds.listConnections("%s.%s" % (rig_root, _SEAMS_ATTR)) or []:
        if cmds.objExists(d) and cmds.nodeType(d) == DEFORMER_TYPE:
            reorder_zipper_to_end(d)
            done.append(d)
    return done
