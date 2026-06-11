# -*- coding: utf-8 -*-
"""EdgeRail: mesh edge selection -> ordered vertex path -> arc-length samples
(ARCHITECTURE.md sec.2).

The graph-ordering core (``order_edge_chain``) is PURE and fully unit-tested
without Maya. The om2-backed ``EdgeRail`` wraps it: it reads edge->vertex
connectivity and world positions through ``maya.api.OpenMaya`` only.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from .rail import RailData, RailSource
from .sampling import resample_with_index
from .math_util import vsub, normalize
from ._compat import string_types

try:
    from maya.api import OpenMaya as om  # type: ignore
except ImportError:  # importable without Maya (CI / pytest)
    om = None


class EdgeOrderError(ValueError):
    """Raised when a selected edge set cannot be ordered into a single chain."""


def order_edge_chain(edges):
    # type: (list) -> tuple
    """Order an unordered set of edges into a single vertex chain.

    edges : iterable of (v0, v1) vertex-id pairs (hashable ids).
    Returns (ordered_vertex_ids, is_closed).

    Rules (sec.2):
      * build the vertex adjacency graph;
      * degree-1 vertices are open-chain endpoints, all-degree-2 is a closed loop;
      * any vertex of degree > 2 (a branch), more than two endpoints, or a
        disconnected set is illegal -> EdgeOrderError, and NO partial result.
    """
    # --- build deduped adjacency, preserving first-seen vertex order --------- #
    adj = {}
    order_seen = []
    edge_keys = set()
    for e in edges:
        if len(e) != 2:
            raise EdgeOrderError("edge must be a pair, got %r" % (e,))
        a, b = e[0], e[1]
        if a == b:
            raise EdgeOrderError("degenerate edge (loop) on vertex %r" % (a,))
        key = frozenset((a, b))
        if key in edge_keys:
            continue  # tolerate duplicate selection of the same edge
        edge_keys.add(key)
        for v in (a, b):
            if v not in adj:
                adj[v] = set()
                order_seen.append(v)
        adj[a].add(b)
        adj[b].add(a)

    if not edge_keys:
        raise EdgeOrderError("no edges supplied")

    # --- classify vertices --------------------------------------------------- #
    endpoints = []
    for v in order_seen:
        deg = len(adj[v])
        if deg > 2:
            raise EdgeOrderError(
                "branching vertex %r has degree %d (expected <= 2)" % (v, deg)
            )
        if deg == 1:
            endpoints.append(v)

    if len(endpoints) == 0:
        is_closed = True
        start = order_seen[0]
    elif len(endpoints) == 2:
        is_closed = False
        start = endpoints[0]
    else:
        raise EdgeOrderError(
            "expected 0 (loop) or 2 (open) endpoints, found %d -- the selection "
            "is branched or disconnected" % (len(endpoints),)
        )

    # --- walk the chain ------------------------------------------------------ #
    ordered = [start]
    visited = set()
    cur = start
    while True:
        nxt = None
        for cand in adj[cur]:
            k = frozenset((cur, cand))
            if k in visited:
                continue
            nxt = cand
            break
        if nxt is None:
            break
        visited.add(frozenset((cur, nxt)))
        cur = nxt
        if is_closed and cur == start:
            break  # closed loop returned to start; do not re-append it
        ordered.append(cur)

    # --- validate full coverage (single connected component) ----------------- #
    if len(visited) != len(edge_keys):
        raise EdgeOrderError(
            "edge set is disconnected: walked %d of %d edges from one component"
            % (len(visited), len(edge_keys))
        )
    expected_v = len(order_seen)
    if len(set(ordered)) != expected_v:
        raise EdgeOrderError(
            "chain covers %d of %d vertices (disconnected/branched)"
            % (len(set(ordered)), expected_v)
        )
    return ordered, is_closed


# --------------------------------------------------------------------------- #
# om2-backed concrete rail
# --------------------------------------------------------------------------- #
def _require_maya():
    if om is None:
        raise RuntimeError(
            "EdgeRail requires Maya (maya.api.OpenMaya); unavailable here."
        )


class EdgeRail(RailSource):
    """Rail sourced from a set of mesh edges on a single mesh."""

    def __init__(self, dag_path, edge_ids):
        # type: (object, list) -> None
        _require_maya()
        self._dag = dag_path           # om.MDagPath to the mesh shape
        self._edge_ids = list(edge_ids)
        self._ordered_vids = None
        self._is_closed = None

    # -- construction ------------------------------------------------------- #
    @classmethod
    def from_handle(cls, handle):
        """Build from a rig_spec handle: a list of edge component strings
        ('mesh.e[i]') OR an (dag_path_string, [edge_ids]) tuple.
        """
        _require_maya()
        if isinstance(handle, (list, tuple)) and len(handle) == 2 \
                and isinstance(handle[0], string_types) \
                and isinstance(handle[1], (list, tuple)):
            sel = om.MSelectionList()
            sel.add(handle[0])
            dag = sel.getDagPath(0)
            return cls(dag, list(handle[1]))
        return cls.from_components(list(handle))

    @classmethod
    def from_components(cls, edge_strings):
        """Build from edge component strings like 'pCubeShape1.e[3]'.

        All edges must belong to the SAME mesh object (sec.8 validation).
        """
        _require_maya()
        if not edge_strings:
            raise ValueError("EdgeRail.from_components: empty edge list")
        sel = om.MSelectionList()
        for s in edge_strings:
            sel.add(s)
        dag = None
        edge_ids = []
        for i in range(sel.length()):
            d, comp = sel.getComponent(i)
            if dag is None:
                dag = d
            elif d.fullPathName() != dag.fullPathName():
                raise ValueError(
                    "EdgeRail: edges span multiple objects (%s vs %s)"
                    % (dag.fullPathName(), d.fullPathName())
                )
            if comp.isNull():
                raise ValueError("EdgeRail: selection %r is not a component" % (s,))
            it = om.MFnSingleIndexedComponent(comp)
            edge_ids.extend(it.getElements())
        return cls(dag, edge_ids)

    # -- ordering ----------------------------------------------------------- #
    def _ensure_ordered(self):
        if self._ordered_vids is not None:
            return
        _require_maya()
        edge_iter = om.MItMeshEdge(self._dag)
        pairs = []
        for eid in self._edge_ids:
            edge_iter.setIndex(eid)
            pairs.append((edge_iter.vertexId(0), edge_iter.vertexId(1)))
        self._ordered_vids, self._is_closed = order_edge_chain(pairs)

    def is_closed(self):
        self._ensure_ordered()
        return self._is_closed

    def ordered_vertex_ids(self):
        self._ensure_ordered()
        return list(self._ordered_vids)

    # -- world positions of ordered verts ----------------------------------- #
    def _ordered_world_points(self):
        self._ensure_ordered()
        mesh = om.MFnMesh(self._dag)
        all_pts = mesh.getPoints(om.MSpace.kWorld)
        pts = []
        for vid in self._ordered_vids:
            p = all_pts[vid]
            pts.append((p.x, p.y, p.z))
        return pts

    # -- RailSource contract ------------------------------------------------ #
    def sample(self, n):
        # type: (int) -> RailData
        pts = self._ordered_world_points()
        samples, nearest = resample_with_index(pts, n, self.is_closed())
        bind = [self._ordered_vids[i] for i in nearest]
        return RailData(samples, bind)

    def tangent_at(self, i):
        pts = self._ordered_world_points()
        if len(pts) < 2:
            return (0.0, 0.0, 0.0)
        j = min(max(i, 0), len(pts) - 1)
        if j == 0:
            return normalize(vsub(pts[1], pts[0]))
        if j == len(pts) - 1:
            return normalize(vsub(pts[-1], pts[-2]))
        return normalize(vsub(pts[j + 1], pts[j - 1]))

    def bind_handle(self):
        return self.ordered_vertex_ids()

    # -- build-layer driver wiring ------------------------------------------ #
    def world_plug(self):
        """Plug to connect into a deformer rail input (mesh world geometry)."""
        return "%s.worldMesh[0]" % (self._dag.fullPathName(),)

    def driver_vertex_ids(self):
        """Edge rails feed the mesh + this ordered vertex-id list to the
        deformer so it samples the right poly-line each frame."""
        return self.ordered_vertex_ids()

    def shape_name(self):
        return self._dag.fullPathName()
