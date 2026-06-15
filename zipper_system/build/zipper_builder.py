# -*- coding: utf-8 -*-
"""Build orchestrator (ARCHITECTURE.md sec.8, sec.10).

``build(rig_spec)`` is the single entry point. It:
  1. pre-validates the whole spec (zero side effects on failure);
  2. opens an undo chunk so any mid-build error rolls back with no orphan nodes;
  3. drives a cancellable progress window over the seams;
  4. dispatches each seam to the dynamic or morph mechanic.

cmds + maya.api only; no Qt.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from maya import cmds

from ..core.rail import from_spec as rail_from_spec
from ..core.seam import Seam
from .validate import validate, resolve_target, resolve_morph_target
from . import build_dynamic
from . import build_morph

_PLUGIN_NODE_TYPE = "ddZipperDeformer"
_PLUGIN_MODULE_NAME = "zipperSystem"


class ZipperValidationError(RuntimeError):
    """Raised when a rig_spec fails pre-validation; carries the report."""

    def __init__(self, report):
        self.report = report
        lines = list(report.errors)
        for idx in sorted(report.seam_errors):
            for msg in report.seam_errors[idx]:
                lines.append("seam %d: %s" % (idx, msg))
        super(ZipperValidationError, self).__init__(
            "rig_spec validation failed:\n  " + "\n  ".join(lines))


def ensure_plugin_loaded():
    """Load the pure-Python deformer plugin if not already loaded.

    The node type may be provided by the installed module plug-in
    ('zipperSystem') or, in a dev checkout, by loading the package file
    directly. We first check whether the node type is already registered so we
    never double-register it.
    """
    try:
        if _PLUGIN_NODE_TYPE in (cmds.allNodeTypes() or []):
            return
    except Exception:
        pass
    # Prefer the installed module plug-in (on the Maya plug-in path).
    try:
        if cmds.pluginInfo(_PLUGIN_MODULE_NAME, query=True, loaded=True):
            return
    except RuntimeError:
        pass
    try:
        cmds.loadPlugin(_PLUGIN_MODULE_NAME, quiet=True)
        return
    except RuntimeError:
        pass
    # Dev fallback: load the package deformer file by absolute path.
    from ..deformer import dd_zipper_deformer as ddmod
    cmds.loadPlugin(ddmod.__file__, quiet=True)


def _seam_from_spec(seam_spec):
    # type: (dict) -> Seam
    rail_a = rail_from_spec(seam_spec["rail_a"])
    rail_b = rail_from_spec(seam_spec["rail_b"])
    return Seam(
        rail_a,
        rail_b,
        pair_count=int(seam_spec.get("pair_count", 30)),
        feather=float(seam_spec.get("feather", 0.15)),
        direction=seam_spec.get("direction", "both"),
        invert=bool(seam_spec.get("invert", False)),
        controller=seam_spec.get("controller", ""),
    )


def build(rig_spec, validate_first=True):
    # type: (dict, bool) -> str
    """Build the zipper rig described by rig_spec; return the rig-root node.

    Raises ZipperValidationError (before touching the scene) on invalid input.
    Any error during construction rolls the whole chunk back.
    """
    if validate_first:
        report = validate(rig_spec)
        if not report.ok:
            raise ZipperValidationError(report)

    mechanic = rig_spec["mechanic"]
    # Deform target: a mesh (mesh mode / inferred from edges) or a NURBS curve
    # (curve mode -- rails drive a separately-picked target curve).
    target, target_kind = resolve_target(rig_spec)
    morph_target = resolve_morph_target(rig_spec)
    seams_spec = rig_spec["seams"]

    if mechanic == "dynamic":
        ensure_plugin_loaded()

    rig_root = None
    opened = False
    progress = False
    try:
        cmds.undoInfo(openChunk=True)
        opened = True

        rig_root = cmds.group(empty=True, name="%s_zipperRig" % rig_spec["name"])

        cmds.progressWindow(
            title="Building Zipper",
            progress=0, status="Preparing...",
            isInterruptable=True, maxValue=len(seams_spec))
        progress = True

        for i, seam_spec in enumerate(seams_spec):
            if cmds.progressWindow(query=True, isCancelled=True):
                raise RuntimeError("build cancelled by user")
            cmds.progressWindow(
                edit=True, step=1, status="Seam %d / %d" % (i + 1, len(seams_spec)))

            seam = _seam_from_spec(seam_spec)
            if mechanic == "dynamic":
                build_dynamic.build_seam_dynamic(
                    target, seam, i, rig_root, target_kind)
            else:
                build_morph.build_seam_morph(
                    target, morph_target, seam, i, rig_root)

        return rig_root

    except Exception:
        if progress:
            cmds.progressWindow(endProgress=True)
            progress = False
        if opened:
            cmds.undoInfo(closeChunk=True)
            opened = False
        try:
            cmds.undo()  # roll the whole chunk back -> no orphan nodes
        except RuntimeError:
            pass
        raise
    finally:
        if progress:
            cmds.progressWindow(endProgress=True)
        if opened:
            cmds.undoInfo(closeChunk=True)
