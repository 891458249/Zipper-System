# -*- coding: utf-8 -*-
"""ddZipperDeformer -- dynamic-midline zipper (ARCHITECTURE.md sec.A).

Pure-Python ``maya.api`` MPxDeformerNode. One instance per seam. Every frame it
reads the two driver rails (curve or mesh, fed in world space), arc-length
samples them to ``pairCount`` pairs, computes the live midline and pulls each
seam vertex toward it by the wipe weight -> the seal line follows the mouth in
real time, no C++ and no recompile across Maya 2022.5 - 2025.3.

deform() per affected vertex (its pair k):
    m_k   = 1/2 (a_k + b_k)
    w     = envelope * paint_v * wipe_weight(k, ...)
    p_out = lerp(p_in, m_k, w)

This module may be ``loadPlugin``-ed directly. It requires the ``zipper_system``
package to be importable in Maya (on sys.path / PYTHONPATH) so it can reuse the
pure ``core`` math -- the single source of the wipe formula.
"""

# Python 3.7-common syntax only.

from maya.api import OpenMaya as om
from maya.api import OpenMayaAnim as oma

from zipper_system.core import math_util as mu
from zipper_system.core import sampling as sp


def maya_useNewAPI():
    """Tell Maya this plugin uses the API 2.0 (om2) objects."""
    pass


_DIRECTIONS = ("both", "ltr", "rtl")


class DDZipperDeformer(oma.MPxDeformerNode):
    """Dynamic midline zipper deformer (one per seam)."""

    kTypeName = "ddZipperDeformer"
    # Dev-range typeId (0x00000 - 0x7ffff). Replace with a registered block id
    # before any external distribution to avoid collisions.
    kTypeId = om.MTypeId(0x0007D7A1)

    # attribute MObjects (populated in initialize)
    aRailA = None
    aRailB = None
    aRailAVerts = None
    aRailBVerts = None
    aPairCount = None
    aZip = None
    aFeather = None
    aDirection = None
    aInvert = None
    aFlipB = None
    aCorrA = None
    aCorrB = None

    def __init__(self):
        super(DDZipperDeformer, self).__init__()

    @staticmethod
    def creator():
        return DDZipperDeformer()

    # --------------------------------------------------------------------- #
    # attribute setup
    # --------------------------------------------------------------------- #
    @staticmethod
    def initialize():
        cls = DDZipperDeformer
        gAttr = om.MFnGenericAttribute()
        nAttr = om.MFnNumericAttribute()
        eAttr = om.MFnEnumAttribute()
        tAttr = om.MFnTypedAttribute()

        out_geom = oma.MPxGeometryFilter.outputGeom

        # -- driver rails: accept curve OR mesh (R1) ----------------------- #
        cls.aRailA = gAttr.create("railA", "rla")
        gAttr.addDataType(om.MFnData.kNurbsCurve)
        gAttr.addDataType(om.MFnData.kMesh)
        gAttr.storable = False
        gAttr.keyable = False
        om.MPxNode.addAttribute(cls.aRailA)
        om.MPxNode.attributeAffects(cls.aRailA, out_geom)

        cls.aRailB = gAttr.create("railB", "rlb")
        gAttr.addDataType(om.MFnData.kNurbsCurve)
        gAttr.addDataType(om.MFnData.kMesh)
        gAttr.storable = False
        gAttr.keyable = False
        om.MPxNode.addAttribute(cls.aRailB)
        om.MPxNode.attributeAffects(cls.aRailB, out_geom)

        # -- ordered vertex ids for mesh rails (empty for curve rails) ----- #
        cls.aRailAVerts = tAttr.create(
            "railAVerts", "rav", om.MFnData.kIntArray,
            om.MFnIntArrayData().create(om.MIntArray()))
        tAttr.storable = True
        tAttr.keyable = False
        om.MPxNode.addAttribute(cls.aRailAVerts)
        om.MPxNode.attributeAffects(cls.aRailAVerts, out_geom)

        cls.aRailBVerts = tAttr.create(
            "railBVerts", "rbv", om.MFnData.kIntArray,
            om.MFnIntArrayData().create(om.MIntArray()))
        tAttr.storable = True
        tAttr.keyable = False
        om.MPxNode.addAttribute(cls.aRailBVerts)
        om.MPxNode.attributeAffects(cls.aRailBVerts, out_geom)

        # -- scalar params ------------------------------------------------- #
        cls.aPairCount = nAttr.create(
            "pairCount", "pc", om.MFnNumericData.kInt, 30)
        nAttr.setMin(2)
        nAttr.keyable = True
        nAttr.storable = True
        om.MPxNode.addAttribute(cls.aPairCount)
        om.MPxNode.attributeAffects(cls.aPairCount, out_geom)

        cls.aZip = nAttr.create("zip", "zip", om.MFnNumericData.kFloat, 0.0)
        nAttr.setMin(0.0)
        nAttr.setMax(1.0)
        nAttr.keyable = True
        nAttr.storable = True
        om.MPxNode.addAttribute(cls.aZip)
        om.MPxNode.attributeAffects(cls.aZip, out_geom)

        cls.aFeather = nAttr.create(
            "feather", "ft", om.MFnNumericData.kFloat, 0.15)
        nAttr.setMin(0.0)
        nAttr.setMax(1.0)
        nAttr.keyable = True
        nAttr.storable = True
        om.MPxNode.addAttribute(cls.aFeather)
        om.MPxNode.attributeAffects(cls.aFeather, out_geom)

        cls.aDirection = eAttr.create(
            "direction", "dir", 0)
        eAttr.addField("both", 0)
        eAttr.addField("ltr", 1)
        eAttr.addField("rtl", 2)
        eAttr.keyable = True
        eAttr.storable = True
        om.MPxNode.addAttribute(cls.aDirection)
        om.MPxNode.attributeAffects(cls.aDirection, out_geom)

        # invertWipe: resolves the sec.3.3 formula/prose contradiction by making
        # the closing direction switchable; False = "ends -> center" (prose).
        cls.aInvert = nAttr.create(
            "invertWipe", "iw", om.MFnNumericData.kBoolean, False)
        nAttr.keyable = True
        nAttr.storable = True
        om.MPxNode.addAttribute(cls.aInvert)
        om.MPxNode.attributeAffects(cls.aInvert, out_geom)

        # flipB: rail B was authored opposite to rail A; the build aligns them
        # and sets this so live B sampling matches the baked corrB orientation.
        cls.aFlipB = nAttr.create(
            "flipB", "fb", om.MFnNumericData.kBoolean, False)
        nAttr.keyable = False
        nAttr.storable = True
        om.MPxNode.addAttribute(cls.aFlipB)
        om.MPxNode.attributeAffects(cls.aFlipB, out_geom)

        # -- baked correspondence: pair k <-> final_mesh vertex id --------- #
        cls.aCorrA = tAttr.create(
            "corrA", "ca", om.MFnData.kIntArray,
            om.MFnIntArrayData().create(om.MIntArray()))
        tAttr.storable = True
        tAttr.keyable = False
        om.MPxNode.addAttribute(cls.aCorrA)
        om.MPxNode.attributeAffects(cls.aCorrA, out_geom)

        cls.aCorrB = tAttr.create(
            "corrB", "cb", om.MFnData.kIntArray,
            om.MFnIntArrayData().create(om.MIntArray()))
        tAttr.storable = True
        tAttr.keyable = False
        om.MPxNode.addAttribute(cls.aCorrB)
        om.MPxNode.attributeAffects(cls.aCorrB, out_geom)

    # --------------------------------------------------------------------- #
    # helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _read_int_array(data_block, attr):
        # type: (object, object) -> list
        try:
            handle = data_block.inputValue(attr)
        except RuntimeError:
            return []
        obj = handle.data()
        if obj.isNull():
            return []
        if not obj.hasFn(om.MFn.kIntArrayData):
            return []
        arr = om.MFnIntArrayData(obj).array()
        return [int(x) for x in arr]

    @staticmethod
    def _sample_rail_world(data_obj, n, ordered_vids):
        # type: (object, int, list) -> list
        """Sample a world-space rail (curve or mesh) to n arc-length points."""
        if data_obj is None or data_obj.isNull():
            return None
        if data_obj.hasFn(om.MFn.kNurbsCurve):
            fn = om.MFnNurbsCurve(data_obj)
            length = fn.length()
            if length <= 1e-9:
                p = fn.getPointAtParam(
                    fn.findParamFromLength(0.0), om.MSpace.kObject)
                return [(p.x, p.y, p.z)] * n
            closed = fn.form in (
                om.MFnNurbsCurve.kClosed, om.MFnNurbsCurve.kPeriodic)
            denom = float(n) if closed else float(n - 1)
            out = []
            for k in range(n):
                s = (k / denom) * length
                prm = fn.findParamFromLength(s)
                p = fn.getPointAtParam(prm, om.MSpace.kObject)
                out.append((p.x, p.y, p.z))
            return out
        if data_obj.hasFn(om.MFn.kMesh):
            fn = om.MFnMesh(data_obj)
            pts = fn.getPoints(om.MSpace.kObject)
            if ordered_vids:
                poly = [(pts[v].x, pts[v].y, pts[v].z) for v in ordered_vids]
            else:
                poly = [(p.x, p.y, p.z) for p in pts]
            return sp.resample_polyline(poly, n, False)
        return None

    # --------------------------------------------------------------------- #
    # deform
    # --------------------------------------------------------------------- #
    def deform(self, data_block, geo_iter, world_matrix, multi_index):
        envelope = data_block.inputValue(
            oma.MPxGeometryFilter.envelope).asFloat()
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
                    p_local = geo_iter.position()
                    p_world = p_local * world_matrix
                    m = mids[k]
                    out_world = om.MPoint(
                        p_world.x + (m[0] - p_world.x) * w,
                        p_world.y + (m[1] - p_world.y) * w,
                        p_world.z + (m[2] - p_world.z) * w,
                    )
                    geo_iter.setPosition(out_world * inv_matrix)
            geo_iter.next()


# --------------------------------------------------------------------------- #
# plugin entry points (om2). Registration is routed through the compat layer so
# the project keeps a single (de)register surface (ARCHITECTURE.md sec.7/A).
# --------------------------------------------------------------------------- #
def initializePlugin(plugin_mobject):
    from zipper_system.compat import register_plugin
    register_plugin(
        plugin_mobject,
        DDZipperDeformer.kTypeName,
        DDZipperDeformer.kTypeId,
        DDZipperDeformer.creator,
        DDZipperDeformer.initialize,
        om.MPxNode.kDeformerNode,
    )


def uninitializePlugin(plugin_mobject):
    from zipper_system.compat import deregister_plugin
    deregister_plugin(plugin_mobject, DDZipperDeformer.kTypeId)
