# -*- coding: utf-8 -*-
"""Build orchestrator (curve-only).

``build(rig_spec)`` is the single entry point. It pre-validates, opens an undo
chunk (so any mid-build error rolls back with no orphan nodes), drives a
cancellable progress window, and conforms each seam's two rails onto its mid
curve.
"""
from __future__ import absolute_import, division, print_function

import contextlib

from maya import cmds

from .validate import validate
from . import build_dynamic
from . import build_native


@contextlib.contextmanager
def undo_chunk():
    """Group every scene edit done inside into a single undoable chunk, so the
    whole operation reverts with one Ctrl+Z. Nestable (Maya nests chunks)."""
    cmds.undoInfo(openChunk=True)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)

_PLUGIN_NODE_TYPE = "ddZipperDeformer"
_PLUGIN_MODULE_NAME = "zipperSystem"
_DEFAULT_BUILD_MODE = "native"

# Discoverable metadata stamped onto each rig_root so the Manage tab (and any
# scripted caller) can enumerate every zipper rig in a scene and show what it is
# without having to walk its node graph. ``zipperRigRoot`` is the enumeration
# primary key; the rest are best-effort descriptors (legacy rigs built before
# this stamp existed are still found via their zipperSeams/zipperNativeNodes
# message arrays -- see action.zipper_action.list_rigs).
RIG_ROOT_ATTR = "zipperRigRoot"
RIG_NAME_ATTR = "zipperRigName"
RIG_MODE_ATTR = "zipperBuildMode"
RIG_SEAMCOUNT_ATTR = "zipperSeamCount"
RIG_CONTROLLERS_ATTR = "zipperControllers"


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
    """Load the pure-Python deformer plugin if its node type is not registered."""
    try:
        if _PLUGIN_NODE_TYPE in (cmds.allNodeTypes() or []):
            return
    except Exception:
        pass
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
    from ..deformer import dd_zipper_deformer as ddmod
    cmds.loadPlugin(ddmod.__file__, quiet=True)


def _seam_controllers(seams_spec):
    """De-duplicated, order-preserving controller names across all seams."""
    seen = []
    for seam in seams_spec:
        ctrl = (seam.get("controller") or "").strip()
        if ctrl and ctrl not in seen:
            seen.append(ctrl)
    return seen


def _stamp_rig_root(rig_root, rig_spec, mode, seams_spec):
    """Tag rig_root with discoverable metadata for the Manage tab.

    addAttr only when missing, then setAttr. Wrapped so a stamping failure never
    fails the build -- the rig is fully functional without the descriptors (it
    still falls back to its zipperSeams / zipperNativeNodes arrays)."""
    try:
        if not cmds.attributeQuery(RIG_ROOT_ATTR, node=rig_root, exists=True):
            cmds.addAttr(rig_root, longName=RIG_ROOT_ATTR,
                         attributeType="bool", defaultValue=True)
        cmds.setAttr("%s.%s" % (rig_root, RIG_ROOT_ATTR), True)

        for attr in (RIG_NAME_ATTR, RIG_MODE_ATTR, RIG_CONTROLLERS_ATTR):
            if not cmds.attributeQuery(attr, node=rig_root, exists=True):
                cmds.addAttr(rig_root, longName=attr, dataType="string")
        cmds.setAttr("%s.%s" % (rig_root, RIG_NAME_ATTR),
                     rig_spec.get("name", ""), type="string")
        cmds.setAttr("%s.%s" % (rig_root, RIG_MODE_ATTR), mode, type="string")
        cmds.setAttr("%s.%s" % (rig_root, RIG_CONTROLLERS_ATTR),
                     ",".join(_seam_controllers(seams_spec)), type="string")

        if not cmds.attributeQuery(RIG_SEAMCOUNT_ATTR, node=rig_root,
                                   exists=True):
            cmds.addAttr(rig_root, longName=RIG_SEAMCOUNT_ATTR,
                         attributeType="long")
        cmds.setAttr("%s.%s" % (rig_root, RIG_SEAMCOUNT_ATTR), len(seams_spec))
    except Exception as exc:                               # noqa: BLE001
        # Best-effort: a missing/failed stamp degrades to legacy fallback.
        try:
            cmds.warning("Zipper System: rig_root metadata stamp skipped (%s)"
                         % exc)
        except Exception:
            pass


def build(rig_spec, validate_first=True):
    # type: (dict, bool) -> str
    """Build the curve zipper described by rig_spec; return the rig-root node."""
    if validate_first:
        report = validate(rig_spec)
        if not report.ok:
            raise ZipperValidationError(report)

    seams_spec = rig_spec["seams"]
    # build_mode: "native" (default, plugin-free stock DG nodes -- downstream
    # needs no plugin) | "deformer" (compact custom-deformer build). Only the
    # deformer branch needs the plugin, so native skips loading it entirely.
    mode = rig_spec.get("build_mode", _DEFAULT_BUILD_MODE)
    builder = build_native if mode == "native" else build_dynamic
    if mode != "native":
        ensure_plugin_loaded()

    rig_root = None
    opened = False
    progress = False
    try:
        cmds.undoInfo(openChunk=True)
        opened = True
        rig_root = cmds.group(empty=True, name="%s_zipperRig" % rig_spec["name"])

        cmds.progressWindow(
            title="Building Zipper", progress=0, status="Preparing...",
            isInterruptable=True, maxValue=len(seams_spec))
        progress = True

        for i, seam_spec in enumerate(seams_spec):
            if cmds.progressWindow(query=True, isCancelled=True):
                raise RuntimeError("build cancelled by user")
            cmds.progressWindow(
                edit=True, step=1,
                status="Seam %d / %d" % (i + 1, len(seams_spec)))
            builder.build_seam(seam_spec, i, rig_root)

        # Stamp discoverable metadata once all seams exist (so zipperSeamCount
        # reflects the real built count). Inside the chunk -> reverts with undo.
        _stamp_rig_root(rig_root, rig_spec, mode, seams_spec)

        return rig_root

    except Exception:
        if progress:
            cmds.progressWindow(endProgress=True)
            progress = False
        if opened:
            cmds.undoInfo(closeChunk=True)
            opened = False
        try:
            cmds.undo()
        except RuntimeError:
            pass
        raise
    finally:
        if progress:
            cmds.progressWindow(endProgress=True)
        if opened:
            cmds.undoInfo(closeChunk=True)


def delete_rig(rig_root):
    # type: (str) -> None
    """Delete a built rig and all its helper nodes, leaving no orphans.

    The native build's helper nodes are plain DG nodes (not under rig_root in
    the DAG), so deleting the group alone would strip them. They are message-
    tagged onto rig_root.zipperNativeNodes[] (and deformer nodes onto
    .zipperSeams[]); collect both and delete them, then the group.
    """
    if not (rig_root and cmds.objExists(rig_root)):
        return
    with undo_chunk():
        extra = []
        for attr in (build_native.NATIVE_NODES_ATTR, "zipperSeams"):
            if cmds.attributeQuery(attr, node=rig_root, exists=True):
                extra.extend(
                    cmds.listConnections("%s.%s" % (rig_root, attr)) or [])
        doomed = [n for n in set(extra) if cmds.objExists(n)]
        if doomed:
            cmds.delete(doomed)
        if cmds.objExists(rig_root):
            cmds.delete(rig_root)
