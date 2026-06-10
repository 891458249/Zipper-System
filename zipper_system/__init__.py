# -*- coding: utf-8 -*-
"""Zipper System -- generic rail-stitching rig for Autodesk Maya.

Layering (see ARCHITECTURE.md sec.4):
    core/     pure domain logic (no cmds / no Qt; om2 only for data access)
    build/    application services orchestrating the Maya node graph
    deformer/ pure-Python om2 MPxDeformerNode
    action/   framework binding (rig_spec)
    ui/        PySide2/6 panels (only depend on build/core, via compat)
    compat/   PySide2<->PySide6 + plugin register/deregister shim

Compatible with Maya 2022.5.1 - 2025.3 (Python 3.7 -> 3.11).
Only Python-3.7-common syntax is used throughout.
"""

__version__ = "0.1.0"
