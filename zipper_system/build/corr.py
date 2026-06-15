# -*- coding: utf-8 -*-
"""Bake the pair<->target-component correspondence (ARCHITECTURE.md sec.A).

For each sampled pair k we find the deform target's component (mesh vertex or
NURBS curve CV) nearest a_k (corrA[k]) and nearest b_k (corrB[k]). The deformer
stores these as int arrays and uses them to know which membership components
belong to which pair. The target may be a MESH (vertices) or a CURVE (CVs) -- the
deformer iterates either identically via MItGeometry. om2 only.
"""
from __future__ import absolute_import, division, print_function

from maya.api import OpenMaya as om


def _target_dag(name):
    sel = om.MSelectionList()
    sel.add(name)
    dag = sel.getDagPath(0)
    try:
        dag.extendToShape()
    except RuntimeError:
        pass
    return dag


def target_kind(name):
    """Return 'mesh' | 'curve' | None for the named deform target."""
    try:
        dag = _target_dag(name)
    except RuntimeError:
        return None
    if dag.hasFn(om.MFn.kMesh):
        return "mesh"
    if dag.hasFn(om.MFn.kNurbsCurve):
        return "curve"
    return None


def _target_world_points(name):
    """Return (MPointArray of component world positions, kind)."""
    dag = _target_dag(name)
    if dag.hasFn(om.MFn.kMesh):
        return om.MFnMesh(dag).getPoints(om.MSpace.kWorld), "mesh"
    if dag.hasFn(om.MFn.kNurbsCurve):
        return om.MFnNurbsCurve(dag).cvPositions(om.MSpace.kWorld), "curve"
    raise ValueError("target %r is neither a mesh nor a NURBS curve" % (name,))


def _nearest_index(points, target):
    """Linear nearest-component search; target is an (x,y,z) tuple."""
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


def bake_correspondence(target, pairs):
    # type: (str, list) -> tuple
    """Return (corrA, corrB) -- target component ids per pair.

    *target* is a mesh or NURBS curve. *pairs* is a list of (a_k, b_k) world
    points (from Seam.sample_pairs).
    """
    pts, _kind = _target_world_points(target)
    corr_a = []
    corr_b = []
    for (a_k, b_k) in pairs:
        corr_a.append(_nearest_index(pts, a_k))
        corr_b.append(_nearest_index(pts, b_k))
    return corr_a, corr_b
