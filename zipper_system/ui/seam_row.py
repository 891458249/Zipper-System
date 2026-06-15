# -*- coding: utf-8 -*-
"""Single seam row widget (curve-only).

A seam is three NURBS curves picked top-to-bottom: Rail A, Mid Curve, Rail B.
The mid curve sits between the two rails (it is the seam line they zip onto).
Each picker has a '<' capture button (NURBS curve selection) and a '?' help
bubble. All Qt via compat. Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt
from .i18n import tr
from .help_button import HelpButton

QtWidgets = qt.QtWidgets
Signal = qt.Signal


class CurvePicker(QtWidgets.QWidget):
    """One labelled NURBS-curve picker: label + '<' + read-only field + help."""

    changed = Signal()

    def __init__(self, label_key, help_key, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._label_key = label_key
        self._handle = None

        self.label = QtWidgets.QLabel(tr(label_key))
        self.label.setMinimumWidth(70)
        self.pick_btn = QtWidgets.QPushButton("<")
        self.pick_btn.setFixedWidth(24)
        self.pick_btn.setToolTip(tr("pick_tip"))
        self.field = QtWidgets.QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText(tr("nothing_picked"))

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.label)
        lay.addWidget(self.pick_btn)
        lay.addWidget(self.field, 1)
        lay.addWidget(HelpButton(help_key))

        self.pick_btn.clicked.connect(self._on_pick)

    def _on_pick(self):
        from ..build import selection
        try:
            self._handle = selection.get_selected_curve()
            self.field.setText(self._handle)
            self.changed.emit()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, tr("pick_warn"), str(exc))

    def handle(self):
        return self._handle

    def retranslate(self):
        self.label.setText(tr(self._label_key))
        self.pick_btn.setToolTip(tr("pick_tip"))
        self.field.setPlaceholderText(tr("nothing_picked"))


class SeamRow(QtWidgets.QWidget):
    """A seam = Rail A + Mid Curve + Rail B (mid between the rails)."""

    changed = Signal()

    def __init__(self, index, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.index = index
        self.rail_a = CurvePicker("rail_a", "rail_a")
        self.mid = CurvePicker("mid_curve", "mid_curve")
        self.rail_b = CurvePicker("rail_b", "rail_b")

        self._box = QtWidgets.QGroupBox(tr("seam_title").format(index))
        inner = QtWidgets.QVBoxLayout(self._box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.addWidget(self.rail_a)
        inner.addWidget(self.mid)
        inner.addWidget(self.rail_b)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._box)

        for p in (self.rail_a, self.mid, self.rail_b):
            p.changed.connect(self.changed)

    def set_title(self, index):
        self.index = index
        self._box.setTitle(tr("seam_title").format(index))

    def seam_spec(self):
        return {
            "rail_a": self.rail_a.handle(),
            "mid": self.mid.handle(),
            "rail_b": self.rail_b.handle(),
        }

    def set_error(self, has_error, tooltip=""):
        self._box.setStyleSheet(
            "QGroupBox { border: 1px solid #c0392b; }" if has_error else "")
        self._box.setToolTip(tooltip)

    def retranslate(self):
        self._box.setTitle(tr("seam_title").format(self.index))
        self.rail_a.retranslate()
        self.mid.retranslate()
        self.rail_b.retranslate()
