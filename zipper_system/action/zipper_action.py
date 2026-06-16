# -*- coding: utf-8 -*-
"""ZipperAction -- the framework-facing wrapper (ARCHITECTURE.md sec.10 P2).

A thin, dependency-light facade adapting the new ``rig_spec`` (sec.C) so the
tool can be driven from a shelf button, a menu, a script, or an external
ActionCore-style framework, without those callers needing to know the build /
ui module layout. No Qt import at module load (the UI is imported lazily).
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.


class ZipperAction(object):
    """Facade over validate / build / UI for the Zipper System."""

    label = "Zipper System"
    name = "zipperSystem"

    # -- headless API ------------------------------------------------------ #
    @staticmethod
    def validate(rig_spec):
        """Validate a rig_spec; returns a build.validate.ValidationReport."""
        from ..build.validate import validate as _validate
        return _validate(rig_spec)

    @staticmethod
    def build(rig_spec):
        """Validate then build; returns the rig-root node name.

        Raises build.zipper_builder.ZipperValidationError on bad input (before
        any scene change) or re-raises a rolled-back build error.
        """
        from ..build import zipper_builder
        return zipper_builder.build(rig_spec)

    @staticmethod
    def delete_rig(rig_root):
        """Delete a built rig and all its helper nodes (no orphans left)."""
        from ..build import zipper_builder
        return zipper_builder.delete_rig(rig_root)

    @staticmethod
    def delete_rigs(roots):
        """Delete several rigs in ONE undo chunk (loops delete_rig)."""
        from ..build import zipper_builder
        with zipper_builder.undo_chunk():
            for root in list(roots or []):
                zipper_builder.delete_rig(root)

    # -- traceability ------------------------------------------------------ #
    @staticmethod
    def _created_nodes(root):
        """Unique scene nodes this rig created (message-tagged on the root).

        Spans both the deformer build (``zipperSeams[]``) and the native build
        (``zipperNativeNodes[]``); used by list/select. Never includes the
        user's own input curves / controllers -- only nodes the rig built."""
        from maya import cmds
        from ..build.build_native import NATIVE_NODES_ATTR
        nodes = []
        for attr in (NATIVE_NODES_ATTR, "zipperSeams"):
            if cmds.attributeQuery(attr, node=root, exists=True):
                for n in (cmds.listConnections(
                        "%s.%s" % (root, attr)) or []):
                    if cmds.objExists(n) and n not in nodes:
                        nodes.append(n)
        return nodes

    @staticmethod
    def list_rigs():
        """Enumerate every zipper rig in the scene (best-effort metadata).

        A transform is a rig if it carries the ``zipperRigRoot`` stamp OR (legacy
        fallback, for rigs built before the stamp existed) one of the
        ``zipperSeams`` / ``zipperNativeNodes`` message arrays. Each dict:
            {root, name, mode, seams, controllers, nodes}
        All attribute reads are guarded so legacy rigs still list. Sorted by
        name; root de-duplicated."""
        from maya import cmds
        from ..build import zipper_builder as zb
        from ..build.build_native import NATIVE_NODES_ATTR

        def _has(node, attr):
            return cmds.attributeQuery(attr, node=node, exists=True)

        def _get_str(node, attr):
            if _has(node, attr):
                try:
                    return cmds.getAttr("%s.%s" % (node, attr)) or ""
                except Exception:
                    return ""
            return ""

        # Gather candidate roots from the stamp + both legacy message arrays.
        roots = []
        seen = set()
        for attr in (zb.RIG_ROOT_ATTR, "zipperSeams", NATIVE_NODES_ATTR):
            for node in (cmds.ls("*.%s" % attr, objectsOnly=True,
                                 long=True) or []):
                full = cmds.ls(node, long=True)
                if not full:
                    continue
                full = full[0]
                if full not in seen and cmds.objExists(full):
                    seen.add(full)
                    roots.append(full)

        rigs = []
        for root in roots:
            # name: explicit stamp, else inferred from the '<name>_zipperRig' node
            name = _get_str(root, zb.RIG_NAME_ATTR)
            if not name:
                short = root.split("|")[-1]
                name = short[:-len("_zipperRig")] \
                    if short.endswith("_zipperRig") else short

            mode = _get_str(root, zb.RIG_MODE_ATTR) or "?"

            if _has(root, zb.RIG_SEAMCOUNT_ATTR):
                try:
                    seams = cmds.getAttr(
                        "%s.%s" % (root, zb.RIG_SEAMCOUNT_ATTR))
                except Exception:
                    seams = "?"
            elif _has(root, "zipperSeams"):
                # Legacy deformer rig: one seam tag per rail deformer is a rough
                # node count, not a seam count, so report it as unknown.
                seams = "?"
            else:
                seams = "?"

            rigs.append({
                "root": root,
                "name": name,
                "mode": mode,
                "seams": seams,
                "controllers": _get_str(root, zb.RIG_CONTROLLERS_ATTR),
                "nodes": len(ZipperAction._created_nodes(root)),
            })

        rigs.sort(key=lambda r: (r["name"], r["root"]))
        return rigs

    @staticmethod
    def select_rig(root):
        """Select a rig for tracing: the rig_root plus every node it created.

        Deliberately excludes the user's input curves / controllers so the
        selection shows exactly what the plugin owns."""
        from maya import cmds
        if not (root and cmds.objExists(root)):
            return []
        sel = [root] + ZipperAction._created_nodes(root)
        cmds.select(sel, replace=True)
        return sel

    @staticmethod
    def reorder_to_chain_end(rig_root):
        """Push this rig's zipper deformers to the end of their rail chains.

        Use after skinning rails that were built (deformer mode) BEFORE the skin,
        so the zipper composes correctly (runs downstream of skinCluster).
        """
        from ..build.reorder import reorder_rig_to_chain_end
        return reorder_rig_to_chain_end(rig_root)

    # -- interactive ------------------------------------------------------- #
    @staticmethod
    def show_ui():
        """Open the Zipper System panel (lazy Qt import)."""
        from ..ui import show
        return show()

    # -- convenience: run from a shelf/menu -------------------------------- #
    def __call__(self):
        return self.show_ui()


def run():
    """Module-level shortcut for shelf buttons: ``zipper_action.run()``."""
    return ZipperAction().show_ui()
