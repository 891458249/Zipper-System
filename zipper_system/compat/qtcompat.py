# -*- coding: utf-8 -*-
"""Qt + Maya-plugin compatibility shim (ARCHITECTURE.md sec.7).

Goal: a *single* import surface for the UI layer so that no module ever does
``from PySide2 import ...`` directly. This lets the exact same UI code run on:

    Maya 2022.5 / 2023 / 2024  ->  PySide2 (Qt 5.15) + shiboken2
    Maya 2025.3               ->  PySide6 (Qt 6.5)  + shiboken6

Contract exported (see sec.7 of the blueprint):
    wrap_instance(ptr, base)        -> wrap a C++ pointer into a Qt object
    CheckState.CHECKED / UNCHECKED  -> scope-stable Qt enum constants
    main_maya_window()              -> Maya main window as a QWidget
    register_plugin(...) / deregister_plugin(...)  -> om2 node (de)registration

Also re-exports QtCore / QtGui / QtWidgets / Signal / Slot / QAction /
QRegularExpression and an ``exec_dialog`` helper that bridges exec_() vs exec().

Everything here must stay import-safe *outside* Maya (so unit tests and the
``core`` layer never explode merely by importing the package). Qt and om2 are
therefore imported defensively.
"""

# NOTE: Python 3.7-common syntax only. No walrus, no match, no 3.8+ typing
# features. Type hints are kept in comments / strings where given.


# --------------------------------------------------------------------------- #
# Qt binding selection (PySide6 first -- it is the future-facing one, and only
# Maya 2025+ ships it; older Mayas only have PySide2 so the fallback is taken).
# --------------------------------------------------------------------------- #
QtCore = None
QtGui = None
QtWidgets = None
Signal = None
Slot = None
QT_BINDING = None

_shiboken_wrap = None

try:
    from PySide6 import QtCore as _QtCore
    from PySide6 import QtGui as _QtGui
    from PySide6 import QtWidgets as _QtWidgets

    QtCore = _QtCore
    QtGui = _QtGui
    QtWidgets = _QtWidgets
    Signal = QtCore.Signal
    Slot = QtCore.Slot
    QT_BINDING = "PySide6"
    try:
        from shiboken6 import wrapInstance as _shiboken_wrap  # type: ignore
    except ImportError:
        _shiboken_wrap = None
except ImportError:
    try:
        from PySide2 import QtCore as _QtCore
        from PySide2 import QtGui as _QtGui
        from PySide2 import QtWidgets as _QtWidgets

        QtCore = _QtCore
        QtGui = _QtGui
        QtWidgets = _QtWidgets
        Signal = QtCore.Signal
        Slot = QtCore.Slot
        QT_BINDING = "PySide2"
        try:
            from shiboken2 import wrapInstance as _shiboken_wrap  # type: ignore
        except ImportError:
            _shiboken_wrap = None
    except ImportError:
        # No Qt at all (headless / CI). The module is still importable; only the
        # UI-facing helpers will raise if actually used.
        QT_BINDING = None


# --------------------------------------------------------------------------- #
# QAction moved QtWidgets -> QtGui in Qt6.
# --------------------------------------------------------------------------- #
QAction = None
if QtGui is not None and hasattr(QtGui, "QAction"):
    QAction = QtGui.QAction            # Qt6 / PySide6
elif QtWidgets is not None and hasattr(QtWidgets, "QAction"):
    QAction = QtWidgets.QAction        # Qt5 / PySide2


# --------------------------------------------------------------------------- #
# QRegExp (Qt5) -> QRegularExpression (Qt6). We always expose the Qt6 name; on
# Qt5 we fall back to QRegExp so callers have a single symbol to target.
# --------------------------------------------------------------------------- #
QRegularExpression = None
if QtCore is not None:
    if hasattr(QtCore, "QRegularExpression"):
        QRegularExpression = QtCore.QRegularExpression
    elif hasattr(QtCore, "QRegExp"):
        QRegularExpression = QtCore.QRegExp


# --------------------------------------------------------------------------- #
# CheckState enum: Qt5 exposes Qt.Checked; Qt6 scopes it as
# Qt.CheckState.Checked. We resolve once and hand back stable constants so UI
# code never has to branch.
# --------------------------------------------------------------------------- #
class _CheckStateConst(object):
    """Resolved Qt check-state constants (scope-stable across Qt5/Qt6)."""

    CHECKED = 2
    UNCHECKED = 0
    PARTIALLY_CHECKED = 1


def _resolve_check_state():
    # type: () -> _CheckStateConst
    const = _CheckStateConst()
    if QtCore is None:
        return const
    qt = QtCore.Qt
    # Qt6: Qt.CheckState.Checked (an enum member). Qt5: Qt.Checked (int-like).
    if hasattr(qt, "CheckState"):
        try:
            const.CHECKED = int(qt.CheckState.Checked.value)
            const.UNCHECKED = int(qt.CheckState.Unchecked.value)
            const.PARTIALLY_CHECKED = int(qt.CheckState.PartiallyChecked.value)
            return const
        except (AttributeError, TypeError):
            pass
    if hasattr(qt, "Checked"):
        const.CHECKED = int(qt.Checked)
        const.UNCHECKED = int(qt.Unchecked)
        const.PARTIALLY_CHECKED = int(qt.PartiallyChecked)
    return const


CheckState = _resolve_check_state()


# --------------------------------------------------------------------------- #
# wrap_instance: shiboken2.wrapInstance vs shiboken6.wrapInstance.
# --------------------------------------------------------------------------- #
def wrap_instance(ptr, base=None):
    # type: (int, object) -> object
    """Wrap a C++ pointer (int) into a Qt object of type ``base``.

    ``base`` defaults to QWidget. Raises RuntimeError if no shiboken binding is
    available (i.e. running outside Maya).
    """
    if _shiboken_wrap is None:
        raise RuntimeError(
            "wrap_instance: no shiboken binding available "
            "(running outside Maya?)."
        )
    if base is None:
        if QtWidgets is None:
            raise RuntimeError("wrap_instance: QtWidgets unavailable.")
        base = QtWidgets.QWidget
    return _shiboken_wrap(int(ptr), base)


# --------------------------------------------------------------------------- #
# main_maya_window: Maya main window wrapped as a QWidget (for parenting).
# --------------------------------------------------------------------------- #
def main_maya_window():
    # type: () -> object
    """Return Maya's main window as a QWidget, or None if unavailable."""
    try:
        from maya import OpenMayaUI as omui  # type: ignore
    except ImportError:
        return None
    ptr = None
    # API differs slightly across versions; both names have existed.
    if hasattr(omui.MQtUtil, "mainWindow"):
        ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    try:
        return wrap_instance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# exec_dialog: exec_() (Qt5) vs exec() (Qt6, exec_ kept as deprecated alias on
# most builds but be safe).
# --------------------------------------------------------------------------- #
def exec_dialog(dialog):
    # type: (object) -> int
    """Modally execute a QDialog regardless of Qt5/Qt6 method naming."""
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


# --------------------------------------------------------------------------- #
# Maya plugin (de)registration -- om2 path, no C++/.mll (ARCHITECTURE.md sec.A).
#
# These are the *single* entry points used by deformer/ to (un)register the
# pure-Python MPxDeformerNode. Implemented here so the whole project has one
# compat surface. om2 is imported lazily so this module stays import-safe in CI.
# --------------------------------------------------------------------------- #
def register_plugin(
    mobject,
    type_name,
    type_id,
    creator,
    initialize,
    node_type=None,
):
    # type: (object, str, object, object, object, object) -> None
    """Register a node on the given plugin MObject via MFnPlugin.

    Parameters mirror ``MFnPlugin.registerNode``:
        mobject     the MObject passed to initializePlugin()
        type_name   node type name string
        type_id     MTypeId
        creator     node creator callable
        initialize  node attribute-initializer callable
        node_type   MPxNode subclass kind; defaults to kDeformerNode.

    Idempotent: silently ignores "already registered" errors so reloads during
    development do not explode.
    """
    from maya.api import OpenMaya as om  # type: ignore

    if node_type is None:
        node_type = om.MPxNode.kDeformerNode
    plugin = om.MFnPlugin(mobject)
    try:
        plugin.registerNode(
            type_name, type_id, creator, initialize, node_type
        )
    except RuntimeError as exc:
        # Re-registering an already-loaded type raises; tolerate it on reload.
        if "already registered" not in str(exc):
            raise


def deregister_plugin(mobject, type_id):
    # type: (object, object) -> None
    """Deregister a node type from the given plugin MObject."""
    from maya.api import OpenMaya as om  # type: ignore

    plugin = om.MFnPlugin(mobject)
    try:
        plugin.deregisterNode(type_id)
    except RuntimeError as exc:
        if "not found" not in str(exc) and "not registered" not in str(exc):
            raise
