# -*- coding: utf-8 -*-
"""Single seam row widget (curve-only).

A seam is one Mid Curve (picked at the top) plus an ordered list of N rail
curves (N >= 1, default 2) below it, each of which zips onto the mid curve. The
rail count is editable per seam via the Rails '+' / '-' buttons. Each picker has
a '<' capture button (NURBS curve selection) and a '?' help bubble. All Qt via
compat. Python 2.7 / 3.x compatible.
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

    def __init__(self, label_key, help_key, parent=None, label_arg=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._label_key = label_key
        self._label_arg = label_arg     # format slot for "Rail {0}" labels
        self._handle = None

        self.label = QtWidgets.QLabel(self._label_text())
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

    def _label_text(self):
        text = tr(self._label_key)
        if self._label_arg is not None:
            try:
                text = text.format(self._label_arg)
            except (IndexError, KeyError):
                pass
        return text

    def set_label_arg(self, arg):
        """Renumber a 'Rail {0}' picker after add/remove."""
        self._label_arg = arg
        self.label.setText(self._label_text())

    def retranslate(self):
        self.label.setText(self._label_text())
        self.pick_btn.setToolTip(tr("pick_tip"))
        self.field.setPlaceholderText(tr("nothing_picked"))


class SeamRow(QtWidgets.QWidget):
    """A seam = one Mid Curve (top) + N rail curves (>= 1, default 2).

    Emits ``sizeChanged`` whenever the rail count changes so the host list can
    refresh its item sizeHint (otherwise the new rail row gets clipped).
    """

    changed = Signal()
    sizeChanged = Signal()

    _MIN_RAILS = 1
    _DEFAULT_RAILS = 2

    def __init__(self, index, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.index = index
        self._rails = []

        # Mid curve on top: it is the seam line every rail zips onto.
        self.mid = CurvePicker("mid_curve", "mid_curve")

        # Rails header: "Rails" + add/remove buttons (each with a help bubble).
        self._rails_label = QtWidgets.QLabel(tr("rails"))
        self.add_rail_btn = QtWidgets.QPushButton(tr("add_rail"))
        self.add_rail_btn.setMinimumWidth(28)
        self.rem_rail_btn = QtWidgets.QPushButton(tr("remove_rail"))
        self.rem_rail_btn.setMinimumWidth(28)
        hdr = QtWidgets.QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.addWidget(self._rails_label)
        hdr.addWidget(self.add_rail_btn)
        hdr.addWidget(HelpButton("add_rail"))
        hdr.addWidget(self.rem_rail_btn)
        hdr.addWidget(HelpButton("remove_rail"))
        hdr.addStretch(1)

        # Dynamic container holding the N rail pickers.
        self._rails_container = QtWidgets.QWidget()
        self._rails_lay = QtWidgets.QVBoxLayout(self._rails_container)
        self._rails_lay.setContentsMargins(0, 0, 0, 0)
        self._rails_lay.setSpacing(2)

        self._box = QtWidgets.QGroupBox(tr("seam_title").format(index))
        inner = QtWidgets.QVBoxLayout(self._box)
        inner.setContentsMargins(6, 4, 6, 4)
        inner.addWidget(self.mid)
        inner.addLayout(hdr)
        inner.addWidget(self._rails_container)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._box)

        self.mid.changed.connect(self.changed)
        self.add_rail_btn.clicked.connect(self._on_add_rail)
        self.rem_rail_btn.clicked.connect(self._on_remove_rail)

        for _ in range(self._DEFAULT_RAILS):
            self._append_rail(notify=False)
        self._update_remove_enabled()

    # -- rail add / remove --------------------------------------------------- #
    def _append_rail(self, notify=True):
        picker = CurvePicker("rail_n", "rail_n", label_arg=len(self._rails))
        picker.changed.connect(self.changed)
        self._rails.append(picker)
        self._rails_lay.addWidget(picker)
        self._update_remove_enabled()
        if notify:
            self.changed.emit()
            self.sizeChanged.emit()

    def _on_add_rail(self):
        self._append_rail()

    def _on_remove_rail(self):
        if len(self._rails) <= self._MIN_RAILS:
            return
        picker = self._rails.pop()
        self._rails_lay.removeWidget(picker)
        picker.setParent(None)
        picker.deleteLater()
        self._update_remove_enabled()
        self.changed.emit()
        self.sizeChanged.emit()

    def _update_remove_enabled(self):
        self.rem_rail_btn.setEnabled(len(self._rails) > self._MIN_RAILS)

    # -- queries / state ----------------------------------------------------- #
    def set_title(self, index):
        self.index = index
        self._box.setTitle(tr("seam_title").format(index))

    def seam_spec(self):
        return {
            "mid": self.mid.handle(),
            "rails": [p.handle() for p in self._rails],
        }

    def set_error(self, has_error, tooltip=""):
        self._box.setStyleSheet(
            "QGroupBox { border: 1px solid #c0392b; }" if has_error else "")
        self._box.setToolTip(tooltip)

    def retranslate(self):
        self._box.setTitle(tr("seam_title").format(self.index))
        self._rails_label.setText(tr("rails"))
        self.add_rail_btn.setText(tr("add_rail"))
        self.rem_rail_btn.setText(tr("remove_rail"))
        self.mid.retranslate()
        for p in self._rails:
            p.retranslate()
