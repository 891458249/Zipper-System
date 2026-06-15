# -*- coding: utf-8 -*-
"""CurveRail: NURBS curve sampled by arc length (ARCHITECTURE.md sec.2).

om2-backed (MFnNurbsCurve). Sampling uses native arc-length parameterisation
(findParamFromLength) so the resulting points are evenly spaced by length, which
is exactly the t_k = k/(N-1) contract from sec.3.1.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from .rail import RailData, RailSource
from .math_util import normalize, vsub
from ._compat import string_types

try:
    from maya.api import OpenMaya as om  # type: ignore
except ImportError:  # importable without Maya
    om = None


def _require_maya():
    if om is None:
        raise RuntimeError(
            "CurveRail requires Maya (maya.api.OpenMaya); unavailable here."
        )


class CurveRail(RailSource):
    """Rail sourced from a NURBS curve."""

    def __init__(self, dag_path):
        _require_maya()
        self._dag = dag_path           # om.MDagPath to the curve shape
        self._fn = om.MFnNurbsCurve(dag_path)

    @classmethod
    def from_handle(cls, handle):
        """Build from a rig_spec handle: a curve transform/shape name string,
        or an om.MDagPath.
        """
        _require_maya()
        if isinstance(handle, string_types):
            sel = om.MSelectionList()
            sel.add(handle)
            dag = sel.getDagPath(0)
            # extend to the shape if a transform was given
            try:
                dag.extendToShape()
            except RuntimeError:
                pass
            return cls(dag)
        return cls(handle)

    # -- arc-length parameters ---------------------------------------------- #
    def _params(self, n):
        if n < 1:
            raise ValueError("n must be >= 1, got %r" % (n,))
        length = self._fn.length()
        form = self._fn.form
        is_closed = form in (om.MFnNurbsCurve.kClosed, om.MFnNurbsCurve.kPeriodic)
        params = []
        if n == 1 or length <= 1e-9:
            p0 = self._fn.findParamFromLength(0.0)
            return [p0] * n, is_closed
        denom = float(n) if is_closed else float(n - 1)
        for k in range(n):
            s = (k / denom) * length
            params.append(self._fn.findParamFromLength(s))
        return params, is_closed

    # -- RailSource contract ------------------------------------------------ #
    def sample(self, n):
        # type: (int) -> RailData
        params, _closed = self._params(n)
        pts = []
        for prm in params:
            p = self._fn.getPointAtParam(prm, om.MSpace.kWorld)
            pts.append((p.x, p.y, p.z))
        # Curve bind handle = the curve param at each sample (sec.2).
        return RailData(pts, list(params))

    def tangent_at(self, i):
        params, _closed = self._params(max(i + 1, 2))
        prm = params[min(i, len(params) - 1)]
        t = self._fn.tangent(prm, om.MSpace.kWorld)
        return normalize((t.x, t.y, t.z))

    def bind_handle(self):
        return ("curve", self._dag.fullPathName())

    # -- build-layer driver wiring ------------------------------------------ #
    def world_plug(self):
        """Plug to connect into a deformer rail input (curve world geometry)."""
        return "%s.worldSpace[0]" % (self._dag.fullPathName(),)

    def driver_vertex_ids(self):
        """Curve rails carry no ordered vertex ids (returns empty list)."""
        return []

    def shape_name(self):
        return self._dag.fullPathName()

    def component_world_points(self):
        """Return (world CV positions, CV ids, 'cv') -- the rail's own geometry
        components, used when the rail is the *deformed* geometry (conform mode)."""
        cvs = self._fn.cvPositions(om.MSpace.kWorld)
        pts = [(p.x, p.y, p.z) for p in cvs]
        return pts, list(range(len(pts))), "cv"
