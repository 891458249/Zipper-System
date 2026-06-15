# -*- coding: utf-8 -*-
"""Selection helpers for the UI's '<' pick buttons (ARCHITECTURE.md sec.6).

cmds-only; lives in the build layer so the UI never imports cmds directly
(keeps the 'ui -> build/core' dependency rule, sec.4).
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya import cmds


def get_selected_edges():
    """Return the current edge selection as flattened 'mesh.e[i]' strings.

    Raises ValueError if nothing/!edges are selected or they span objects.
    """
    edges = cmds.filterExpand(
        cmds.ls(selection=True, flatten=True) or [], selectionMask=32) or []
    if not edges:
        raise ValueError("select one or more polygon edges first")
    objs = set(e.split(".")[0] for e in edges)
    if len(objs) > 1:
        raise ValueError("edges span multiple objects: %s" % ", ".join(objs))
    return list(edges)


def get_selected_curve():
    """Return the selected NURBS curve transform's full DAG path.

    Uses long=True so same-named curves resolve to a unique path downstream
    (om.MSelectionList.add on a short name is ambiguous when names collide).
    Raises ValueError if the selection is not a single NURBS curve.
    """
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        raise ValueError("select a NURBS curve first")
    curve = None
    for node in sel:
        shapes = cmds.ls(node, dag=True, type="nurbsCurve", noIntermediate=True)
        if shapes:
            curve = node
            break
    if curve is None:
        raise ValueError("selection is not a NURBS curve")
    return curve


def get_selected_mesh():
    """Return the first selected mesh transform/shape full DAG path."""
    sel = cmds.ls(selection=True, long=True) or []
    for node in sel:
        if cmds.ls(node, dag=True, type="mesh", noIntermediate=True):
            return node
    raise ValueError("select a polygon mesh first")


def get_selected_node():
    """Return the first selected node's full DAG path (any type)."""
    sel = cmds.ls(selection=True, long=True) or []
    if not sel:
        raise ValueError("nothing selected")
    return sel[0]
