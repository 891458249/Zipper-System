# -*- coding: utf-8 -*-
"""Bake the pair<->final_mesh vertex correspondence (ARCHITECTURE.md sec.A).

For each sampled pair k we find the final_mesh vertex nearest a_k (corrA[k]) and
nearest b_k (corrB[k]). The deformer stores these as int arrays and uses them to
know which membership vertices belong to which pair (and thus which wipe weight
and midline to apply). om2 only.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya.api import OpenMaya as om


def _mesh_world_points(mesh_name):
    sel = om.MSelectionList()
    sel.add(mesh_name)
    dag = sel.getDagPath(0)
    dag.extendToShape()
    fn = om.MFnMesh(dag)
    return fn.getPoints(om.MSpace.kWorld)


def _nearest_vertex(points, target):
    """Linear nearest-vertex search; target is an (x,y,z) tuple."""
    tx, ty, tz = target
    best_i = 0
    best_d = None
    for i in range(len(points)):
        p = points[i]
        dx = p.x - tx
        dy = p.y - ty
        dz = p.z - tz
        d = dx * dx + dy * dy + dz * dz
        if best_d is None or d < best_d:
            best_d = d
            best_i = i
    return best_i


def bake_correspondence(final_mesh, pairs):
    # type: (str, list) -> tuple
    """Return (corrA, corrB) -- final_mesh vertex ids per pair.

    pairs: list of (a_k, b_k) world-space point tuples (from Seam.sample_pairs).
    """
    pts = _mesh_world_points(final_mesh)
    corr_a = []
    corr_b = []
    for (a_k, b_k) in pairs:
        corr_a.append(_nearest_vertex(pts, a_k))
        corr_b.append(_nearest_vertex(pts, b_k))
    return corr_a, corr_b
