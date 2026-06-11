# -*- coding: utf-8 -*-
"""Single seam row widget (ARCHITECTURE.md sec.6).

Each rail has an [Edge/Curve] source dropdown, a '<' pick button (which routes
to the matching build.selection helper), a read-only handle display, and a '?'
help bubble. The source *value* is read by combo INDEX (0=edge, 1=curve) so
translating the dropdown labels never breaks the logic. All Qt via compat.
Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt
from .i18n import tr
from .help_button import HelpButton

QtWidgets = qt.QtWidgets
Signal = qt.Signal

_MODES = ("edge", "curve")  # combo index -> rail-spec value


class RailPicker(QtWidgets.QWidget):
    """One rail: source-type dropdown + pick button + handle display + help."""

    changed = Signal()

    def __init__(self, label_key, help_key, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._label_key = label_key
        self._handle = None

        self.label = QtWidgets.QLabel(tr(label_key))
        self.combo = QtWidgets.QComboBox()
        self.combo.addItems([tr("edge"), tr("curve")])  # index 0/1 = edge/curve
        self.pick_btn = QtWidgets.QPushButton("<")
        self.pick_btn.setFixedWidth(24)
        self.pick_btn.setToolTip(tr("pick_tip"))
        self.field = QtWidgets.QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText(tr("nothing_picked"))
        self.help = HelpButton(help_key)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.label)
        lay.addWidget(self.combo)
        lay.addWidget(self.pick_btn)
        lay.addWidget(self.field, 1)
        lay.addWidget(self.help)

        self.pick_btn.clicked.connect(self._on_pick)
        self.combo.currentIndexChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, _idx):
        self._handle = None
        self.field.setText("")
        self.changed.emit()

    def mode(self):
        idx = self.combo.currentIndex()
        return _MODES[idx] if 0 <= idx < len(_MODES) else "edge"

    def _on_pick(self):
        from ..build import selection
        try:
            if self.mode() == "edge":
                handle = selection.get_selected_edges()
                self.field.setText(
                    tr("edges_count").format(len(handle),
                                             handle[0].split(".")[0]))
            else:
                handle = selection.get_selected_curve()
                self.field.setText(handle)
            self._handle = handle
            self.changed.emit()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, tr("pick_warn"), str(exc))

    def get_spec(self):
        return {"type": self.mode(), "handle": self._handle}

    def retranslate(self):
        self.label.setText(tr(self._label_key))
        idx = self.combo.currentIndex()
        self.combo.blockSignals(True)
        self.combo.setItemText(0, tr("edge"))
        self.combo.setItemText(1, tr("curve"))
        self.combo.setCurrentIndex(idx)
        self.combo.blockSignals(False)
        self.pick_btn.setToolTip(tr("pick_tip"))
        self.field.setPlaceholderText(tr("nothing_picked"))


class SeamRow(QtWidgets.QWidget):
    """A seam = two RailPickers (rail A, rail B)."""

    changed = Signal()

    def __init__(self, index, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.index = index
        self.rail_a = RailPicker("rail_a", "rail_a")
        self.rail_b = RailPicker("rail_b", "rail_b")

        self._box = QtWidgets.QGroupBox(tr("seam_title").format(index))
        inner = QtWidgets.QVBoxLayout(self._box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.addWidget(self.rail_a)
        inner.addWidget(self.rail_b)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._box)

        self.rail_a.changed.connect(self.changed)
        self.rail_b.changed.connect(self.changed)

    def set_title(self, index):
        self.index = index
        self._box.setTitle(tr("seam_title").format(index))

    def rails_spec(self):
        return self.rail_a.get_spec(), self.rail_b.get_spec()

    def set_error(self, has_error, tooltip=""):
        self._box.setStyleSheet(
            "QGroupBox { border: 1px solid #c0392b; }" if has_error else "")
        self._box.setToolTip(tooltip)

    def retranslate(self):
        self._box.setTitle(tr("seam_title").format(self.index))
        self.rail_a.retranslate()
        self.rail_b.retranslate()
