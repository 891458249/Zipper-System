# -*- coding: utf-8 -*-
"""Single seam row widget (ARCHITECTURE.md sec.6).

Each rail has an [Edge/Curve] source dropdown, a '<' pick button (which routes
to the matching build.selection helper) and a read-only display of the captured
handle. Hits R1 (curve-or-edge per rail). All Qt access goes through compat.
"""

# Python 3.7-common syntax only.

from ..compat import qtcompat as qt

QtWidgets = qt.QtWidgets
Signal = qt.Signal


class RailPicker(QtWidgets.QWidget):
    """One rail: source-type dropdown + pick button + handle display."""

    changed = Signal()

    def __init__(self, label, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._handle = None

        self.combo = QtWidgets.QComboBox()
        self.combo.addItems(["Edge", "Curve"])
        self.pick_btn = QtWidgets.QPushButton("<")
        self.pick_btn.setFixedWidth(24)
        self.pick_btn.setToolTip("Capture the current selection")
        self.field = QtWidgets.QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText("(nothing picked)")

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QtWidgets.QLabel(label))
        lay.addWidget(self.combo)
        lay.addWidget(self.pick_btn)
        lay.addWidget(self.field, 1)

        self.pick_btn.clicked.connect(self._on_pick)
        self.combo.currentIndexChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, _idx):
        # switching source invalidates the captured handle
        self._handle = None
        self.field.setText("")
        self.changed.emit()

    def mode(self):
        return self.combo.currentText().lower()  # 'edge' | 'curve'

    def _on_pick(self):
        from ..build import selection
        try:
            if self.mode() == "edge":
                handle = selection.get_selected_edges()
                self.field.setText("%d edge(s) on %s"
                                   % (len(handle), handle[0].split(".")[0]))
            else:
                handle = selection.get_selected_curve()
                self.field.setText(handle)
            self._handle = handle
            self.changed.emit()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Pick", str(exc))

    def get_spec(self):
        return {"type": self.mode(), "handle": self._handle}


class SeamRow(QtWidgets.QWidget):
    """A seam = two RailPickers (rail A, rail B)."""

    changed = Signal()

    def __init__(self, index, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.index = index
        self.rail_a = RailPicker("Rail A:")
        self.rail_b = RailPicker("Rail B:")

        box = QtWidgets.QGroupBox("Seam %d" % index)
        inner = QtWidgets.QVBoxLayout(box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.addWidget(self.rail_a)
        inner.addWidget(self.rail_b)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(box)
        self._box = box

        self.rail_a.changed.connect(self.changed)
        self.rail_b.changed.connect(self.changed)

    def set_title(self, index):
        self.index = index
        self._box.setTitle("Seam %d" % index)

    def rails_spec(self):
        return self.rail_a.get_spec(), self.rail_b.get_spec()

    def set_error(self, has_error, tooltip=""):
        self._box.setStyleSheet(
            "QGroupBox { border: 1px solid #c0392b; }" if has_error else "")
        self._box.setToolTip(tooltip)
