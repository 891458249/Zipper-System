# -*- coding: utf-8 -*-
"""Zipper System startup hook (auto-run by Maya at launch).

The module's ``scripts:`` path is on MAYA_SCRIPT_PATH, so Maya executes this
``userSetup.py`` during startup. We defer the actual work until the UI is up,
then:
  1. build the top-level "Zipper System" menu (so the tool is in the menu bar
     immediately -- no Plug-in Manager ticking), and
  2. auto-load the ddZipperDeformer plug-in (so users never have to enable it).

Everything is wrapped defensively: a failure here must never block Maya startup
or other modules' userSetup files. Python 2.7 / 3.x compatible, ASCII only.
"""
from __future__ import absolute_import, division, print_function


def _zipper_system_startup():
    import maya.cmds as cmds
    if cmds.about(query=True, batch=True):
        return
    # 1) top menu
    try:
        from zipper_system.action import build_menu
        build_menu()
    except Exception as exc:                               # noqa: BLE001
        try:
            cmds.warning("Zipper System: menu init failed (%s)" % exc)
        except Exception:
            pass
    # 2) auto-load the deformer plug-in so it shows as Loaded with no manual tick
    try:
        if not cmds.pluginInfo("zipperSystem", query=True, loaded=True):
            cmds.loadPlugin("zipperSystem", quiet=True)
    except Exception:
        pass


try:
    import maya.utils
    maya.utils.executeDeferred(_zipper_system_startup)
except Exception:
    # No maya.utils (e.g. pure mayapy without UR) -> skip silently.
    pass
