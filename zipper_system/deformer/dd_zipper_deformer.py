# -*- coding: utf-8 -*-
"""ddZipperDeformer -- dynamic-midline zipper (ARCHITECTURE.md sec.A).

Pure-Python custom deformer. One instance per seam. Every frame it reads the two
driver rails (curve or mesh, fed in world space), arc-length samples them to
``pairCount`` pairs, computes the live midline and pulls each seam vertex toward
it by the wipe weight -> the seal line follows the mouth in real time. No C++,
no .mll, no recompile across Maya 2022.5 - 2025.3.

deform() per affected vertex (its pair k):
    m_k   = 1/2 (a_k + b_k)
    w     = envelope * paint_v * wipe_weight(k, ...)
    p_out = lerp(p_in, m_k, w)

IMPLEMENTATION NOTE -- why API 1.0 (OpenMayaMPx), not om2
---------------------------------------------------------
The blueprint (sec.A) specified a ``maya.api`` (om2) ``MPxDeformerNode``. In
practice Autodesk only added ``MPxDeformerNode`` to the *Python* API 2.0 in
**Maya 2024**; Maya 2022 / 2023 raise ``AttributeError: ... has no attribute
'MPxDeformerNode'`` when subclassing ``maya.api.OpenMayaAnim``. To cover the full
2022.5.1 - 2025.3 range with one pure-Python implementation we use the **API 1.0**
proxy ``maya.OpenMayaMPx.MPxDeformerNode``, which exists in every version. The
pure-math ``core`` layer (still plain Python, om-free) is reused unchanged, so
the wipe formula remains single-sourced. Geometry sampling here uses API-1.0
function sets (out-parameter style).

Requires the ``zipper_system`` package to be importable in Maya (the module .mod
puts it on the script path).
"""
from __future__ import absolute_import, division, print_function


# Python 2.7 / 3.x dual-compatible; API 1.0 idioms only.

import maya.OpenMaya as om
import maya.OpenMayaMPx as ompx

from zipper_system.core import math_util as mu
from zipper_system.core import sampling as sp


kTypeName = "ddZipperDeformer"
# Dev-range typeId (0x00000 - 0x7ffff). Replace with a registered block id before
# any external distribution to avoid collisions.
kTypeId = om.MTypeId(0x0007D7A1)

_DIRECTIONS = ("both", "ltr", "rtl")


class DDZipperDeformer(ompx.MPxDeformerNode):
    """Dynamic midline zipper deformer (one per seam)."""

    # attribute MObjects (populated in nodeInitializer)
    aRailA = om.MObject()
    aRailB = om.MObject()
    aRailAMatrix = om.MObject()
    aRailBMatrix = om.MObject()
    aRailAVerts = om.MObject()
    aRailBVerts = om.MObject()
    aPairCount = om.MObject()
    aZip = om.MObject()
    aFeather = om.MObject()
    aDirection = om.MObject()
    aInvert = om.MObject()
    aFlipB = om.MObject()
    aCorrA = om.MObject()
    aCorrB = om.MObject()

    def __init__(self):
        ompx.MPxDeformerNode.__init__(self)

    # --------------------------------------------------------------------- #
    # helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _read_int_array(data_block, attr):
        """Return a plain list[int] from an int-array attribute (or [])."""
        try:
            handle = data_block.inputValue(attr)
        except RuntimeError:
            return []
        obj = handle.data()
        if obj.isNull() or not obj.hasFn(om.MFn.kIntArrayData):
            return []
        arr = om.MFnIntArrayData(obj).array()
        return [int(arr[i]) for i in range(arr.length())]

    @staticmethod
    def _to_world(pts, mtx):
        """Lift object-space sample points into world space by mtx.

        Driver geometry arrives through a generic attribute in object space, so
        each sampled point is multiplied by the driver's world matrix. For a
        frozen (identity-matrix) curve this is a no-op."""
        out = []
        for (x, y, z) in pts:
            p = om.MPoint(x, y, z) * mtx
            out.append((p.x, p.y, p.z))
        return out

    @staticmethod
    def _sample_rail_world(data_obj, n, ordered_vids):
        """Sample a world-space rail (curve or mesh) to n arc-length points."""
        if data_obj is None or data_obj.isNull():
            return None
        if data_obj.hasFn(om.MFn.kNurbsCurve):
            fn = om.MFnNurbsCurve(data_obj)
            length = fn.length()
            pt = om.MPoint()
            if length <= 1e-9:
                fn.getPointAtParam(fn.findParamFromLength(0.0), pt,
                                   om.MSpace.kObject)
                return [(pt.x, pt.y, pt.z)] * n
            form = fn.form()
            closed = form in (om.MFnNurbsCurve.kClosed,
                              om.MFnNurbsCurve.kPeriodic)
            denom = float(n) if closed else float(n - 1)
            out = []
            for k in range(n):
                s = (k / denom) * length
                prm = fn.findParamFromLength(s)
                fn.getPointAtParam(prm, pt, om.MSpace.kObject)
                out.append((pt.x, pt.y, pt.z))
            return out
        if data_obj.hasFn(om.MFn.kMesh):
            fn = om.MFnMesh(data_obj)
            pts = om.MPointArray()
            fn.getPoints(pts, om.MSpace.kObject)
            if ordered_vids:
                poly = [(pts[v].x, pts[v].y, pts[v].z) for v in ordered_vids]
            else:
                poly = [(pts[i].x, pts[i].y, pts[i].z)
                        for i in range(pts.length())]
            return sp.resample_polyline(poly, n, False)
        return None

    # --------------------------------------------------------------------- #
    # deform
    # --------------------------------------------------------------------- #
    def deform(self, data_block, geo_iter, world_matrix, multi_index):
        env_attr = ompx.cvar.MPxGeometryFilter_envelope
        envelope = data_block.inputValue(env_attr).asFloat()
        if envelope == 0.0:
            return

        n = data_block.inputValue(self.aPairCount).asInt()
        if n < 2:
            return
        z = data_block.inputValue(self.aZip).asFloat()
        beta = data_block.inputValue(self.aFeather).asFloat()
        dir_idx = data_block.inputValue(self.aDirection).asShort()
        direction = _DIRECTIONS[dir_idx] if 0 <= dir_idx < 3 else "both"
        invert = data_block.inputValue(self.aInvert).asBool()

        vids_a = self._read_int_array(data_block, self.aRailAVerts)
        vids_b = self._read_int_array(data_block, self.aRailBVerts)
        rail_a_obj = data_block.inputValue(self.aRailA).data()
        rail_b_obj = data_block.inputValue(self.aRailB).data()
        a_pts = self._sample_rail_world(rail_a_obj, n, vids_a)
        b_pts = self._sample_rail_world(rail_b_obj, n, vids_b)
        if a_pts is None or b_pts is None:
            return
        # Samples are in the drivers' object space; lift to world via their world
        # matrices (identity for frozen curves, so behaviour is unchanged there).
        a_mtx = data_block.inputValue(self.aRailAMatrix).asMatrix()
        b_mtx = data_block.inputValue(self.aRailBMatrix).asMatrix()
        a_pts = self._to_world(a_pts, a_mtx)
        b_pts = self._to_world(b_pts, b_mtx)
        if data_block.inputValue(self.aFlipB).asBool():
            b_pts = b_pts[::-1]

        corr_a = self._read_int_array(data_block, self.aCorrA)
        corr_b = self._read_int_array(data_block, self.aCorrB)
        vid2k = {}
        for k, vid in enumerate(corr_a):
            if k < n:
                vid2k[vid] = k
        for k, vid in enumerate(corr_b):
            if k < n:
                vid2k[vid] = k
        if not vid2k:
            return

        mids = [mu.midpoint(a_pts[k], b_pts[k]) for k in range(n)]
        wk = [mu.wipe_weight(k, n, z, beta, direction, invert)
              for k in range(n)]

        inv_matrix = world_matrix.inverse()
        geo_iter.reset()
        while not geo_iter.isDone():
            idx = geo_iter.index()
            k = vid2k.get(idx)
            if k is not None:
                paint = self.weightValue(data_block, multi_index, idx)
                w = envelope * paint * wk[k]
                if w > 0.0:
                    p_world = geo_iter.position() * world_matrix
                    m = mids[k]
                    out_world = om.MPoint(
                        p_world.x + (m[0] - p_world.x) * w,
                        p_world.y + (m[1] - p_world.y) * w,
                        p_world.z + (m[2] - p_world.z) * w,
                    )
                    geo_iter.setPosition(out_world * inv_matrix)
            geo_iter.next()


# --------------------------------------------------------------------------- #
# plugin registration (API 1.0)
# --------------------------------------------------------------------------- #
def nodeCreator():
    return ompx.asMPxPtr(DDZipperDeformer())


def _int_array_default():
    return om.MFnIntArrayData().create(om.MIntArray())


def nodeInitializer():
    cls = DDZipperDeformer
    nAttr = om.MFnNumericAttribute()
    eAttr = om.MFnEnumAttribute()
    tAttr = om.MFnTypedAttribute()
    gAttr = om.MFnGenericAttribute()
    mAttr = om.MFnMatrixAttribute()

    out_geom = ompx.cvar.MPxGeometryFilter_outputGeom

    # -- driver rails: accept curve OR mesh (R1) --------------------------- #
    cls.aRailA = gAttr.create("railA", "rla")
    gAttr.addDataAccept(om.MFnData.kNurbsCurve)
    gAttr.addDataAccept(om.MFnData.kMesh)
    gAttr.setStorable(False)
    gAttr.setKeyable(False)
    cls.addAttribute(cls.aRailA)
    cls.attributeAffects(cls.aRailA, out_geom)

    cls.aRailB = gAttr.create("railB", "rlb")
    gAttr.addDataAccept(om.MFnData.kNurbsCurve)
    gAttr.addDataAccept(om.MFnData.kMesh)
    gAttr.setStorable(False)
    gAttr.setKeyable(False)
    cls.addAttribute(cls.aRailB)
    cls.attributeAffects(cls.aRailB, out_geom)

    # -- driver world matrices: lift object-space samples to world --------- #
    cls.aRailAMatrix = mAttr.create("railAMatrix", "ram")
    mAttr.setStorable(False)
    mAttr.setKeyable(False)
    cls.addAttribute(cls.aRailAMatrix)
    cls.attributeAffects(cls.aRailAMatrix, out_geom)

    cls.aRailBMatrix = mAttr.create("railBMatrix", "rbm")
    mAttr.setStorable(False)
    mAttr.setKeyable(False)
    cls.addAttribute(cls.aRailBMatrix)
    cls.attributeAffects(cls.aRailBMatrix, out_geom)

    # -- ordered vertex ids for mesh rails (empty for curve rails) --------- #
    cls.aRailAVerts = tAttr.create("railAVerts", "rav",
                                   om.MFnData.kIntArray, _int_array_default())
    tAttr.setStorable(True)
    tAttr.setKeyable(False)
    cls.addAttribute(cls.aRailAVerts)
    cls.attributeAffects(cls.aRailAVerts, out_geom)

    cls.aRailBVerts = tAttr.create("railBVerts", "rbv",
                                   om.MFnData.kIntArray, _int_array_default())
    tAttr.setStorable(True)
    tAttr.setKeyable(False)
    cls.addAttribute(cls.aRailBVerts)
    cls.attributeAffects(cls.aRailBVerts, out_geom)

    # -- scalar params ----------------------------------------------------- #
    cls.aPairCount = nAttr.create("pairCount", "pc",
                                  om.MFnNumericData.kInt, 30)
    nAttr.setMin(2)
    nAttr.setKeyable(True)
    nAttr.setStorable(True)
    cls.addAttribute(cls.aPairCount)
    cls.attributeAffects(cls.aPairCount, out_geom)

    cls.aZip = nAttr.create("zip", "zip", om.MFnNumericData.kFloat, 0.0)
    nAttr.setMin(0.0)
    nAttr.setMax(1.0)
    nAttr.setKeyable(True)
    nAttr.setStorable(True)
    cls.addAttribute(cls.aZip)
    cls.attributeAffects(cls.aZip, out_geom)

    cls.aFeather = nAttr.create("feather", "ft",
                                om.MFnNumericData.kFloat, 0.15)
    nAttr.setMin(0.0)
    nAttr.setMax(1.0)
    nAttr.setKeyable(True)
    nAttr.setStorable(True)
    cls.addAttribute(cls.aFeather)
    cls.attributeAffects(cls.aFeather, out_geom)

    cls.aDirection = eAttr.create("direction", "dir", 0)
    eAttr.addField("both", 0)
    eAttr.addField("ltr", 1)
    eAttr.addField("rtl", 2)
    eAttr.setKeyable(True)
    eAttr.setStorable(True)
    cls.addAttribute(cls.aDirection)
    cls.attributeAffects(cls.aDirection, out_geom)

    # invertWipe resolves the sec.3.3 formula/prose contradiction by making the
    # closing direction switchable; False = "ends -> center" (the prose).
    cls.aInvert = nAttr.create("invertWipe", "iw",
                               om.MFnNumericData.kBoolean, False)
    nAttr.setKeyable(True)
    nAttr.setStorable(True)
    cls.addAttribute(cls.aInvert)
    cls.attributeAffects(cls.aInvert, out_geom)

    # flipB: rail B authored opposite to A; build aligns them and sets this so
    # live B sampling matches the baked corrB orientation.
    cls.aFlipB = nAttr.create("flipB", "fb",
                              om.MFnNumericData.kBoolean, False)
    nAttr.setKeyable(False)
    nAttr.setStorable(True)
    cls.addAttribute(cls.aFlipB)
    cls.attributeAffects(cls.aFlipB, out_geom)

    # -- baked correspondence: pair k <-> final_mesh vertex id ------------- #
    cls.aCorrA = tAttr.create("corrA", "ca",
                              om.MFnData.kIntArray, _int_array_default())
    tAttr.setStorable(True)
    tAttr.setKeyable(False)
    cls.addAttribute(cls.aCorrA)
    cls.attributeAffects(cls.aCorrA, out_geom)

    cls.aCorrB = tAttr.create("corrB", "cb",
                              om.MFnData.kIntArray, _int_array_default())
    tAttr.setStorable(True)
    tAttr.setKeyable(False)
    cls.addAttribute(cls.aCorrB)
    cls.attributeAffects(cls.aCorrB, out_geom)


def initializePlugin(mobject):
    plugin = ompx.MFnPlugin(mobject, "ZipperSystem", "0.1.0", "Any")
    try:
        plugin.registerNode(
            kTypeName, kTypeId, nodeCreator, nodeInitializer,
            ompx.MPxNode.kDeformerNode)
    except Exception:
        om.MGlobal.displayError(
            "Failed to register node: %s" % kTypeName)
        raise


def uninitializePlugin(mobject):
    plugin = ompx.MFnPlugin(mobject)
    try:
        plugin.deregisterNode(kTypeId)
    except Exception:
        om.MGlobal.displayError(
            "Failed to deregister node: %s" % kTypeName)
        raise
