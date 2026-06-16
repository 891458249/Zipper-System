# -*- coding: utf-8 -*-
"""Main-menu-bar integration for the Zipper System.

Builds a top-level "Zipper System" menu in Maya's main window so the tool is
reachable right after install -- no Plug-in Manager ticking, no command typing.
Invoked automatically by the module's ``userSetup.py`` at startup, and callable
by hand (``from zipper_system.action import build_menu; build_menu()``) to
rebuild without restarting Maya.

Maya menu/UI ops need ``cmds`` / ``mel``; those are imported lazily *inside* the
functions so importing this module stays safe outside Maya (and in pytest).
Python 2.7 / 3.x dual-compatible, ASCII only.
"""
from __future__ import absolute_import, division, print_function


MENU_NAME = "zipperSystemMainMenu"
MENU_LABEL = "Zipper System"


def _main_window():
    import maya.mel as mel
    return mel.eval("$_zs_tmp = $gMainWindow")


def build_menu(*args):
    """Create (or rebuild) the top-level Zipper System menu. No-op in batch."""
    import maya.cmds as cmds
    if cmds.about(query=True, batch=True):
        return None
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)
    cmds.menu(MENU_NAME, parent=_main_window(), label=MENU_LABEL, tearOff=True)
    cmds.menuItem(parent=MENU_NAME, label="Open Zipper System UI",
                  annotation="Open the multi-seam zipper builder panel",
                  command=_open_ui)
    cmds.menuItem(parent=MENU_NAME, divider=True)
    cmds.menuItem(parent=MENU_NAME,
                  label="Reorder zipper after skin / 蒙皮后重排拉链",
                  annotation="Push zipper deformers to the end of their rail "
                             "chains (run after skinning a deformer-mode rig)",
                  command=_reorder_after_skin)
    cmds.menuItem(parent=MENU_NAME, divider=True)
    cmds.menuItem(parent=MENU_NAME, label="Load Deformer Plug-in",
                  annotation="Load the ddZipperDeformer plug-in",
                  command=_load_plugin)
    cmds.menuItem(parent=MENU_NAME, label="Rebuild This Menu",
                  command=build_menu)
    cmds.menuItem(parent=MENU_NAME, divider=True)
    cmds.menuItem(parent=MENU_NAME, label="About...", command=_about)
    return MENU_NAME


def remove_menu(*args):
    import maya.cmds as cmds
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)


# --- menu item callbacks (Maya passes a trailing arg -> accept *args) ------- #
def _open_ui(*args):
    import maya.cmds as cmds
    # Make sure the deformer is available for dynamic builds.
    try:
        from ..build.zipper_builder import ensure_plugin_loaded
        ensure_plugin_loaded()
    except Exception as exc:                               # noqa: BLE001
        cmds.warning("Zipper System: plug-in load skipped (%s)" % exc)
    from .zipper_action import ZipperAction
    ZipperAction.show_ui()


def _reorder_after_skin(*args):
    import maya.cmds as cmds
    # Selected rig roots, else every zipper rig in the scene.
    roots = [n for n in (cmds.ls(selection=True, long=True) or [])
             if cmds.attributeQuery("zipperSeams", node=n, exists=True)]
    if not roots:
        roots = [n for n in (cmds.ls(long=True) or [])
                 if cmds.attributeQuery("zipperSeams", node=n, exists=True)]
    if not roots:
        cmds.warning("Zipper System: no deformer-mode zipper rig found "
                     "(native rigs need no reordering).")
        return
    from .zipper_action import ZipperAction
    total = 0
    for root in roots:
        total += len(ZipperAction.reorder_to_chain_end(root) or [])
    cmds.inViewMessage(
        assistMessage="Zipper reordered after skin (%d deformer(s))." % total,
        position="midCenter", fade=True)


def _load_plugin(*args):
    import maya.cmds as cmds
    try:
        if not cmds.pluginInfo("zipperSystem", query=True, loaded=True):
            cmds.loadPlugin("zipperSystem", quiet=True)
        cmds.inViewMessage(
            assistMessage="Zipper System plug-in loaded.",
            position="midCenter", fade=True)
    except Exception as exc:                               # noqa: BLE001
        cmds.warning("Zipper System: failed to load plug-in (%s)" % exc)


def _about(*args):
    import maya.cmds as cmds
    from .. import __version__
    cmds.confirmDialog(
        title="Zipper System",
        message="Zipper System  v%s\n\nGeneric rail-stitching zipper rig.\n"
                "Maya 2022.5.1 - 2025.3 (pure Python)." % __version__,
        button=["OK"])
