# -*- coding: utf-8 -*-
"""RailSource abstraction + RailData (ARCHITECTURE.md sec.2).

A Rail is an ordered 3D point chain whose source is either a NURBS curve or a
mesh edge loop. The upper layers only ever consume the unified ``RailData``
(points + per-sample bind handles); the Seam pairing / midline / wipe code is
completely agnostic to which concrete source produced it (satisfies R1 + R3).

This module is pure: it defines the interface and a ``from_spec`` factory. The
om2-backed concrete classes (CurveRail / EdgeRail) are imported lazily so the
interface stays importable without Maya.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

import abc


class RailData(object):
    """Result of sampling a rail: aligned points[] and bind[] handles.

    points : list of n 3-tuples in world space.
    bind   : list of n source bind handles (curve param floats for CurveRail,
             vertex ids for EdgeRail). Used by the builder to bake the
             pair<->final_mesh vertex correspondence (sec.A corrA/corrB).
    """

    __slots__ = ("points", "bind")

    def __init__(self, points, bind):
        # type: (list, list) -> None
        if len(points) != len(bind):
            raise ValueError(
                "RailData: points (%d) and bind (%d) length mismatch"
                % (len(points), len(bind))
            )
        self.points = list(points)
        self.bind = list(bind)

    def __len__(self):
        return len(self.points)

    def __repr__(self):
        return "RailData(n=%d)" % (len(self.points),)


def _add_metaclass(metaclass):
    """Class decorator applying *metaclass* on both Py2 and Py3 (six idiom).

    Maya 2022.5.1 may run in Python 2.7 mode (mayapy2); ``class C(metaclass=...)``
    and a bare ``__metaclass__`` attribute are each single-version-only, so we
    rebuild the class through the metaclass in a way both interpreters accept.
    """
    def wrapper(cls):
        orig_vars = cls.__dict__.copy()
        slots = orig_vars.get("__slots__")
        if slots is not None:
            if isinstance(slots, str):
                slots = [slots]
            for slot in slots:
                orig_vars.pop(slot, None)
        orig_vars.pop("__dict__", None)
        orig_vars.pop("__weakref__", None)
        if hasattr(cls, "__qualname__"):
            orig_vars["__qualname__"] = cls.__qualname__
        return metaclass(cls.__name__, cls.__bases__, orig_vars)
    return wrapper


@_add_metaclass(abc.ABCMeta)
class RailSource(object):
    """Abstract base for a sampleable rail (sec.2 contract)."""

    @abc.abstractmethod
    def sample(self, n):
        # type: (int) -> RailData
        """Return n ordered world-space points + bind handles."""
        raise NotImplementedError

    @abc.abstractmethod
    def tangent_at(self, i):
        # type: (int) -> tuple
        """Tangent direction at sample index i (used for midline normals)."""
        raise NotImplementedError

    @abc.abstractmethod
    def bind_handle(self):
        """Source-level rebind info (edge: vertex ids; curve: param/PoCI)."""
        raise NotImplementedError


def from_spec(spec):
    # type: (dict) -> RailSource
    """Factory: build a concrete RailSource from a rig_spec rail entry.

    spec = {"type": "edge" | "curve", "handle": <edges | curve>}
    Dispatches on ``type`` to EdgeRail / CurveRail (sec.C). Concrete classes are
    imported here (lazily) because they require om2.
    """
    if not isinstance(spec, dict):
        raise TypeError("rail spec must be a dict, got %r" % (type(spec),))
    rtype = spec.get("type")
    handle = spec.get("handle")
    if rtype == "curve":
        from .rail_curve import CurveRail
        return CurveRail.from_handle(handle)
    if rtype == "edge":
        from .rail_edge import EdgeRail
        return EdgeRail.from_handle(handle)
    raise ValueError(
        "rail spec 'type' must be 'edge' or 'curve', got %r" % (rtype,)
    )
