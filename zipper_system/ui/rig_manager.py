# -*- coding: utf-8 -*-
"""Manage tab -- list / trace / delete the zipper rigs in the scene.

Lists every zipper rig (via ZipperAction.list_rigs, which also finds legacy rigs
built before the discoverable stamp existed). Each row can be checked; checked
rows can be selected in the scene (for tracing what a rig owns) or deleted
(delete removes only the plugin-created nodes -- the user's input curves and
controllers are kept). Double-clicking a row selects just that rig.

All Qt via the compat shim. Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt
from .i18n import tr
from .help_button import HelpButton

QtWidgets = qt.QtWidgets
QtCore = qt.QtCore

# Column layout of the rig table.
_COL_CHECK = 0
_COL_NAME = 1
_COL_MODE = 2
_COL_SEAMS = 3
_COL_CONTROLLERS = 4
_COL_NODES = 5
_COL_KEYS = ("col_check", "col_name", "col_mode", "col_seams",
             "col_controllers", "col_nodes")


class RigManagerWidget(QtWidgets.QWidget):
    """List, trace and delete zipper rigs in the current scene."""

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._roots = []          # rig_root full path per table row
        self._build_ui()
        self._retranslate()

    # -- construction --------------------------------------------------- #
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton(tr("mgr_refresh"))
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        top.addWidget(HelpButton("mgr_refresh"))
        self.count_label = QtWidgets.QLabel("")
        top.addWidget(self.count_label)
        top.addStretch(1)
        root.addLayout(top)

        self.table = QtWidgets.QTableWidget(0, len(_COL_KEYS))
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        # Rows are read-only except for the checkbox in column 0.
        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        try:
            header.setSectionResizeMode(
                _COL_NAME, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(
                _COL_CONTROLLERS, QtWidgets.QHeaderView.Stretch)
        except (AttributeError, TypeError):
            pass
        self.table.setColumnWidth(_COL_CHECK, 28)
        root.addWidget(self.table, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.select_btn = QtWidgets.QPushButton(tr("mgr_select_scene"))
        self.select_btn.clicked.connect(self._on_select)
        bottom.addWidget(self.select_btn)
        bottom.addWidget(HelpButton("mgr_select_scene"))
        bottom.addStretch(1)
        self.delete_btn = QtWidgets.QPushButton(tr("mgr_delete_selected"))
        self.delete_btn.clicked.connect(self._on_delete)
        bottom.addWidget(self.delete_btn)
        bottom.addWidget(HelpButton("mgr_delete_selected"))
        root.addLayout(bottom)

    # -- language ------------------------------------------------------- #
    def retranslate(self):
        self.refresh_btn.setText(tr("mgr_refresh"))
        self.select_btn.setText(tr("mgr_select_scene"))
        self.delete_btn.setText(tr("mgr_delete_selected"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in _COL_KEYS])
        self._update_count(len(self._roots))

    # -- data ----------------------------------------------------------- #
    def _update_count(self, n):
        self.count_label.setText(tr("mgr_count").format(n))

    def refresh(self):
        """Re-scan the scene and repopulate the table."""
        from ..action.zipper_action import ZipperAction
        try:
            rigs = ZipperAction.list_rigs()
        except Exception:                                  # noqa: BLE001
            rigs = []
        self._roots = [r["root"] for r in rigs]
        self.table.setRowCount(len(rigs))
        for row, rig in enumerate(rigs):
            chk = QtWidgets.QTableWidgetItem()
            chk.setFlags(QtCore.Qt.ItemIsUserCheckable
                         | QtCore.Qt.ItemIsEnabled
                         | QtCore.Qt.ItemIsSelectable)
            chk.setCheckState(QtCore.Qt.Unchecked)
            self.table.setItem(row, _COL_CHECK, chk)
            self._set_cell(row, _COL_NAME, rig["name"])
            self._set_cell(row, _COL_MODE, rig["mode"])
            self._set_cell(row, _COL_SEAMS, rig["seams"])
            self._set_cell(row, _COL_CONTROLLERS, rig["controllers"])
            self._set_cell(row, _COL_NODES, rig["nodes"])
        self._update_count(len(rigs))
        if not rigs:
            self.count_label.setText(tr("mgr_none"))

    def _set_cell(self, row, col, value):
        item = QtWidgets.QTableWidgetItem(u"%s" % value)
        self.table.setItem(row, col, item)

    # -- helpers -------------------------------------------------------- #
    def _checked_rows(self):
        rows = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, _COL_CHECK)
            if item is not None and \
                    int(item.checkState()) == qt.CheckState.CHECKED:
                rows.append(row)
        return rows

    def _root_at(self, row):
        if 0 <= row < len(self._roots):
            return self._roots[row]
        return None

    def _name_at(self, row):
        item = self.table.item(row, _COL_NAME)
        return item.text() if item is not None else u""

    # -- actions -------------------------------------------------------- #
    def _on_double_click(self, row, _col):
        from ..action.zipper_action import ZipperAction
        root = self._root_at(row)
        if root:
            ZipperAction.select_rig(root)

    def _on_select(self):
        from maya import cmds
        from ..action.zipper_action import ZipperAction
        roots = [self._root_at(r) for r in self._checked_rows()]
        roots = [r for r in roots if r]
        if not roots:
            QtWidgets.QMessageBox.information(
                self, tr("mgr_select_scene"), tr("mgr_confirm_none"))
            return
        # Merge the created nodes of every checked rig into one selection.
        sel = []
        for root in roots:
            sel.extend(ZipperAction.select_rig(root) or [])
        if sel:
            cmds.select(sel, replace=True)

    def _on_delete(self):
        from ..action.zipper_action import ZipperAction
        rows = self._checked_rows()
        if not rows:
            QtWidgets.QMessageBox.information(
                self, tr("mgr_confirm_title"), tr("mgr_confirm_none"))
            return
        roots = [self._root_at(r) for r in rows]
        roots = [r for r in roots if r]
        names = u"\n".join(u"  - %s" % self._name_at(r) for r in rows)
        answer = QtWidgets.QMessageBox.question(
            self, tr("mgr_confirm_title"),
            tr("mgr_confirm_text").format(len(roots), names),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if answer != QtWidgets.QMessageBox.Yes:
            return
        ZipperAction.delete_rigs(roots)
        self.refresh()

    # -- lifecycle ------------------------------------------------------ #
    def showEvent(self, event):
        self.refresh()
        super(RigManagerWidget, self).showEvent(event)
