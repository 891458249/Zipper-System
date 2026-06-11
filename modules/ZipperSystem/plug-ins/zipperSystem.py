# -*- coding: utf-8 -*-
"""Maya plug-in entry point for the Zipper System.

Installed via the ZipperSystem.mod module (``plug-ins: plug-ins``). This is a
*thin* wrapper: it re-exports the registration entry points from the real
deformer implementation in the ``zipper_system`` package (which the same .mod
puts on the script path via ``scripts: scripts``). Keeping the logic in the
package means there is a single source of truth -- no duplicated deformer code.

The deformer uses Maya Python API 1.0 (OpenMayaMPx) so it loads on Maya
2022.5.1 - 2025.3 alike (API 2.0 only gained MPxDeformerNode in Maya 2024), so
there is no ``maya_useNewAPI`` flag here -- its absence selects API 1.0.

In Maya:  Windows > Settings/Preferences > Plug-in Manager > zipperSystem
(or)      cmds.loadPlugin("zipperSystem")
"""

from zipper_system.deformer.dd_zipper_deformer import (  # noqa: F401
    initializePlugin,
    uninitializePlugin,
)
