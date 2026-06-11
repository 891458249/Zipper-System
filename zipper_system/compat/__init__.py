# -*- coding: utf-8 -*-
"""Compatibility shims (Qt + Maya plugin registration)."""
from __future__ import absolute_import, division, print_function


from .qtcompat import (  # noqa: F401
    QtCore,
    QtGui,
    QtWidgets,
    Signal,
    Slot,
    QAction,
    QRegularExpression,
    CheckState,
    wrap_instance,
    main_maya_window,
    exec_dialog,
    register_plugin,
    deregister_plugin,
    QT_BINDING,
)
