# -*- coding: utf-8 -*-
"""Zipper System main panel (ARCHITECTURE.md sec.6).

Multi-seam list (add/remove), per-row Edge/Curve toggle, dynamic Pair Count
clamp, Mechanic radio (Dynamic midline / Morph) with morph-mesh gating, plus
Validate (no-build pre-check that highlights bad seams) and Build.

Globals (pair count / feather / direction / controller) are applied to every
seam when assembling the rig_spec; the schema keeps them per-seam, so per-row
overrides are a future extension. All Qt access goes through compat.
"""
from __future__ import absolute_import, division, print_function


# Python 3.7-common syntax only.

from ..compat import qtcompat as qt

QtWidgets = qt.QtWidgets
QtCore = qt.QtCore

_WINDOW_OBJECT = "zipperSystemMainWidget"


class _PickField(QtWidgets.QWidget):
    """A read-only line edit with a '<' button that captures a selection."""

    def __init__(self, getter, placeholder="", parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._getter = getter
        self.field = QtWidgets.QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText(placeholder)
        btn = QtWidgets.QPushButton("<")
        btn.setFixedWidth(24)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(btn)
        lay.addWidget(self.field, 1)
        btn.clicked.connect(self._on_pick)

    def _on_pick(self):
        try:
            self.field.setText(self._getter())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Pick", str(exc))

    def text(self):
        return self.field.text().strip()


class ZipperWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setObjectName(_WINDOW_OBJECT)
        self.setWindowTitle("Zipper System")
        self.setWindowFlags(QtCore.Qt.Window)
        self._seam_rows = []
        self._build_ui()
        self._add_seam()

    # ------------------------------------------------------------------ #
    # construction
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        from ..build import selection

        root = QtWidgets.QVBoxLayout(self)

        # rig name
        form_top = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit("zipperRig")
        form_top.addRow("Rig Name:", self.name_edit)
        root.addLayout(form_top)

        # seams list with add/remove
        seam_box = QtWidgets.QGroupBox("Seams")
        seam_lay = QtWidgets.QVBoxLayout(seam_box)
        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton("+ Add Seam")
        self.rem_btn = QtWidgets.QPushButton("- Remove")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.rem_btn)
        btn_row.addStretch(1)
        seam_lay.addLayout(btn_row)
        self.seam_list = QtWidgets.QListWidget()
        self.seam_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        seam_lay.addWidget(self.seam_list)
        root.addWidget(seam_box, 1)

        # global params
        params = QtWidgets.QFormLayout()
        self.pair_spin = QtWidgets.QSpinBox()
        self.pair_spin.setRange(2, 400)
        self.pair_spin.setValue(30)
        params.addRow("Pair Count:", self.pair_spin)

        self.feather_spin = QtWidgets.QDoubleSpinBox()
        self.feather_spin.setRange(0.0, 1.0)
        self.feather_spin.setSingleStep(0.05)
        self.feather_spin.setValue(0.15)
        params.addRow("Feather (beta):", self.feather_spin)

        self.dir_combo = QtWidgets.QComboBox()
        self.dir_combo.addItems(["both", "ltr", "rtl"])
        params.addRow("Direction:", self.dir_combo)

        self.invert_chk = QtWidgets.QCheckBox(
            "Invert wipe (center -> ends)")
        params.addRow("", self.invert_chk)

        self.final_field = _PickField(
            selection.get_selected_mesh, "head_GEO")
        params.addRow("Final Mesh:", self.final_field)

        self.ctrl_field = _PickField(
            selection.get_selected_node, "jaw_zip_CTRL")
        params.addRow("Controller:", self.ctrl_field)
        root.addLayout(params)

        # mechanic
        mech_box = QtWidgets.QGroupBox("Mechanic")
        mech_lay = QtWidgets.QVBoxLayout(mech_box)
        self.dyn_radio = QtWidgets.QRadioButton("Dynamic midline")
        self.morph_radio = QtWidgets.QRadioButton("Morph")
        self.dyn_radio.setChecked(True)
        self.mech_group = QtWidgets.QButtonGroup(self)
        self.mech_group.addButton(self.dyn_radio)
        self.mech_group.addButton(self.morph_radio)
        mech_lay.addWidget(self.dyn_radio)
        mech_lay.addWidget(self.morph_radio)
        self.morph_field = _PickField(
            selection.get_selected_mesh, "(Morph mode only)")
        mform = QtWidgets.QFormLayout()
        mform.addRow("Morph Mesh:", self.morph_field)
        mech_lay.addLayout(mform)
        root.addWidget(mech_box)

        # actions
        act_row = QtWidgets.QHBoxLayout()
        act_row.addStretch(1)
        self.validate_btn = QtWidgets.QPushButton("Validate")
        self.build_btn = QtWidgets.QPushButton("Build")
        act_row.addWidget(self.validate_btn)
        act_row.addWidget(self.build_btn)
        root.addLayout(act_row)

        # wiring
        self.add_btn.clicked.connect(self._add_seam)
        self.rem_btn.clicked.connect(self._remove_seam)
        self.validate_btn.clicked.connect(self._on_validate)
        self.build_btn.clicked.connect(self._on_build)
        self.morph_radio.toggled.connect(self._on_mechanic_changed)
        self._on_mechanic_changed()

    # ------------------------------------------------------------------ #
    # seam list management
    # ------------------------------------------------------------------ #
    def _add_seam(self):
        from .seam_row import SeamRow
        index = len(self._seam_rows)
        row = SeamRow(index)
        row.changed.connect(self._reclamp_pair_count)
        item = QtWidgets.QListWidgetItem(self.seam_list)
        item.setSizeHint(row.sizeHint())
        self.seam_list.addItem(item)
        self.seam_list.setItemWidget(item, row)
        self._seam_rows.append((item, row))
        self._reclamp_pair_count()

    def _remove_seam(self):
        if len(self._seam_rows) <= 1:
            return
        cur = self.seam_list.currentRow()
        if cur < 0:
            cur = len(self._seam_rows) - 1
        item, _row = self._seam_rows.pop(cur)
        self.seam_list.takeItem(self.seam_list.row(item))
        for new_idx, (it, row) in enumerate(self._seam_rows):
            row.set_title(new_idx)
        self._reclamp_pair_count()

    def _on_mechanic_changed(self, *_):
        is_morph = self.morph_radio.isChecked()
        self.morph_field.setEnabled(is_morph)

    # ------------------------------------------------------------------ #
    # dynamic pair-count clamp (sec.6: fixes the prototype 999999 bug)
    # ------------------------------------------------------------------ #
    def _reclamp_pair_count(self):
        from ..build.validate import seam_cap
        caps = []
        for _item, row in self._seam_rows:
            ra, rb = row.rails_spec()
            cap = seam_cap({"rail_a": ra, "rail_b": rb})
            if cap is not None:
                caps.append(cap)
        if caps:
            top = max(2, min(caps))
            self.pair_spin.setMaximum(top)
            if self.pair_spin.value() > top:
                self.pair_spin.setValue(top)

    # ------------------------------------------------------------------ #
    # spec assembly + actions
    # ------------------------------------------------------------------ #
    def _collect_spec(self):
        mechanic = "morph" if self.morph_radio.isChecked() else "dynamic"
        seams = []
        for _item, row in self._seam_rows:
            ra, rb = row.rails_spec()
            seams.append({
                "rail_a": ra,
                "rail_b": rb,
                "pair_count": self.pair_spin.value(),
                "feather": self.feather_spin.value(),
                "direction": self.dir_combo.currentText(),
                "invert": self.invert_chk.isChecked(),
                "controller": self.ctrl_field.text(),
            })
        spec = {
            "name": self.name_edit.text().strip() or "zipperRig",
            "final_mesh": self.final_field.text(),
            "mechanic": mechanic,
            "morph_mesh": self.morph_field.text() if mechanic == "morph" else "",
            "seams": seams,
        }
        return spec

    def _apply_report(self, report):
        for idx, (_item, row) in enumerate(self._seam_rows):
            msgs = report.seam_errors.get(idx, [])
            row.set_error(bool(msgs), "\n".join(msgs))
        return report

    def _on_validate(self):
        from ..build.validate import validate
        report = self._apply_report(validate(self._collect_spec()))
        if report.ok:
            QtWidgets.QMessageBox.information(
                self, "Validate", "Validation passed.")
        else:
            QtWidgets.QMessageBox.warning(
                self, "Validate", "\n".join(report.errors) or
                "See highlighted seam rows.")

    def _on_build(self):
        from ..build import zipper_builder
        from ..build.validate import validate
        spec = self._collect_spec()
        report = self._apply_report(validate(spec))
        if not report.ok:
            QtWidgets.QMessageBox.warning(
                self, "Build", "Fix validation errors first.")
            return
        try:
            root = zipper_builder.build(spec, validate_first=False)
        except Exception as exc:                       # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Build failed", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self, "Build", "Built rig: %s" % root)


def show():
    """Create (or re-show) the Zipper System panel, parented to Maya."""
    parent = qt.main_maya_window()
    global _INSTANCE
    try:
        _INSTANCE.close()       # noqa: F821
        _INSTANCE.deleteLater()  # noqa: F821
    except Exception:
        pass
    widget = ZipperWidget(parent)
    widget.show()
    globals()["_INSTANCE"] = widget
    return widget
