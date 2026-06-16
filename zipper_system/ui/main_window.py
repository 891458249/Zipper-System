# -*- coding: utf-8 -*-
"""Zipper System host window -- a QTabWidget wrapping the two panels.

Tab 0 = Build  -> the existing ZipperWidget (unchanged, embedded as a child).
Tab 1 = Manage -> RigManagerWidget (list / trace / delete rigs in the scene).

The Build tab owns the language switcher; it emits ``languageChanged`` after it
retranslates itself, and this window relays that to the Manage tab and the tab
titles so the whole UI flips EN/中文 in one place. Switching to the Manage tab
auto-refreshes its list.

All Qt via the compat shim. Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt
from .i18n import tr
from .zipper_widget import ZipperWidget
from .rig_manager import RigManagerWidget

QtWidgets = qt.QtWidgets
QtCore = qt.QtCore

_WINDOW_OBJECT = "zipperSystemMainWindow"


class ZipperMainWindow(QtWidgets.QWidget):
    """Tabbed host for the Build and Manage panels."""

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setObjectName(_WINDOW_OBJECT)
        self.setWindowFlags(QtCore.Qt.Window)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.build_widget = ZipperWidget()
        self.manage_widget = RigManagerWidget()
        self.tabs.addTab(self.build_widget, tr("tab_build"))
        self.tabs.addTab(self.manage_widget, tr("tab_manage"))

        # The language switcher lives on the Build tab; relay its change here so
        # the Manage tab and the tab titles retranslate too.
        self.build_widget.languageChanged.connect(self._retranslate)
        # Refresh the Manage list whenever it becomes the current tab.
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(tr("win_title"))
        self.tabs.setTabText(0, tr("tab_build"))
        self.tabs.setTabText(1, tr("tab_manage"))
        self.manage_widget.retranslate()

    def _on_tab_changed(self, index):
        if self.tabs.widget(index) is self.manage_widget:
            self.manage_widget.refresh()


def show():
    """Create (or re-show) the Zipper System window, parented to Maya."""
    parent = qt.main_maya_window()
    try:
        globals()["_INSTANCE"].close()
        globals()["_INSTANCE"].deleteLater()
    except Exception:
        pass
    window = ZipperMainWindow(parent)
    window.show()
    globals()["_INSTANCE"] = window
    return window
