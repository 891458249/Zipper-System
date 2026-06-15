# -*- coding: utf-8 -*-
"""Zipper System main panel (ARCHITECTURE.md sec.6).

Multi-seam list (add/remove), per-row Edge/Curve toggle, dynamic Pair Count
clamp, Mechanic radio (Dynamic / Morph) with morph-mesh gating, Validate / Build.
Every control carries a '?' help bubble (English/Chinese) and the whole UI
switches language at runtime. All Qt via compat. Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt
from .i18n import tr, set_language, current_language
from .help_button import HelpButton

QtWidgets = qt.QtWidgets
QtCore = qt.QtCore

_WINDOW_OBJECT = "zipperSystemMainWidget"
_DIRS = ("both", "ltr", "rtl")          # direction combo index -> value
_DIR_KEYS = ("dir_both", "dir_ltr", "dir_rtl")
_LANGS = ("en", "zh")                   # language combo index -> code


class _PickField(QtWidgets.QWidget):
    """Read-only line edit + '<' capture button."""

    def __init__(self, getter, placeholder_key, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self._getter = getter
        self._placeholder_key = placeholder_key
        self.field = QtWidgets.QLineEdit()
        self.field.setReadOnly(True)
        self.field.setPlaceholderText(tr(placeholder_key))
        self.btn = QtWidgets.QPushButton("<")
        self.btn.setFixedWidth(24)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.btn)
        lay.addWidget(self.field, 1)
        self.btn.clicked.connect(self._on_pick)

    def _on_pick(self):
        try:
            self.field.setText(self._getter())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, tr("pick_warn"), str(exc))

    def text(self):
        return self.field.text().strip()

    def retranslate(self):
        self.field.setPlaceholderText(tr(self._placeholder_key))


class ZipperWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setObjectName(_WINDOW_OBJECT)
        self.setWindowFlags(QtCore.Qt.Window)
        self._seam_rows = []
        self._labels = {}     # key -> QLabel (for retranslate)
        self._build_ui()
        self._add_seam()
        self._retranslate()

    # ------------------------------------------------------------------ #
    def _label(self, key):
        lbl = QtWidgets.QLabel(tr(key))
        self._labels[key] = lbl
        return lbl

    def _build_ui(self):
        from ..build import selection

        root = QtWidgets.QVBoxLayout(self)

        # -- language switcher (top-right) -------------------------------- #
        lang_row = QtWidgets.QHBoxLayout()
        lang_row.addStretch(1)
        self._lang_label = self._label("language")
        lang_row.addWidget(self._lang_label)
        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItems(["English", u"中文"])
        self.lang_combo.setCurrentIndex(
            _LANGS.index(current_language())
            if current_language() in _LANGS else 0)
        self.lang_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_row.addWidget(self.lang_combo)
        lang_row.addWidget(HelpButton("language"))
        root.addLayout(lang_row)

        # -- rig name ----------------------------------------------------- #
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(self._label("rig_name"))
        self.name_edit = QtWidgets.QLineEdit("zipperRig")
        name_row.addWidget(self.name_edit, 1)
        name_row.addWidget(HelpButton("rig_name"))
        root.addLayout(name_row)

        # -- seams -------------------------------------------------------- #
        self._seams_box = QtWidgets.QGroupBox(tr("seams"))
        seam_lay = QtWidgets.QVBoxLayout(self._seams_box)
        btn_row = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton(tr("add_seam"))
        self.rem_btn = QtWidgets.QPushButton(tr("remove_seam"))
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(HelpButton("add_seam"))
        btn_row.addWidget(self.rem_btn)
        btn_row.addWidget(HelpButton("remove_seam"))
        btn_row.addStretch(1)
        btn_row.addWidget(HelpButton("seams"))
        seam_lay.addLayout(btn_row)
        self.seam_list = QtWidgets.QListWidget()
        self.seam_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        seam_lay.addWidget(self.seam_list)
        root.addWidget(self._seams_box, 1)

        # -- params grid -------------------------------------------------- #
        grid = QtWidgets.QGridLayout()
        r = 0

        self.pair_spin = QtWidgets.QSpinBox()
        self.pair_spin.setRange(2, 400)
        self.pair_spin.setValue(30)
        self._add_grid_row(grid, r, "pair_count", self.pair_spin); r += 1

        self.feather_spin = QtWidgets.QDoubleSpinBox()
        self.feather_spin.setRange(0.0, 1.0)
        self.feather_spin.setSingleStep(0.05)
        self.feather_spin.setValue(0.15)
        self._add_grid_row(grid, r, "feather", self.feather_spin); r += 1

        self.dir_combo = QtWidgets.QComboBox()
        self.dir_combo.addItems([tr(k) for k in _DIR_KEYS])
        self._add_grid_row(grid, r, "direction", self.dir_combo); r += 1

        self.invert_chk = QtWidgets.QCheckBox(tr("invert_wipe"))
        grid.addWidget(self.invert_chk, r, 1)
        grid.addWidget(HelpButton("invert_wipe"), r, 2); r += 1

        self.final_field = _PickField(
            selection.get_selected_mesh, "final_auto")
        self._add_grid_row(grid, r, "final_mesh", self.final_field); r += 1

        self.ctrl_field = _PickField(
            selection.get_selected_node, "nothing_picked")
        self._add_grid_row(grid, r, "controller", self.ctrl_field); r += 1
        root.addLayout(grid)

        # -- mechanic ----------------------------------------------------- #
        self._mech_box = QtWidgets.QGroupBox(tr("mechanic"))
        mech_lay = QtWidgets.QVBoxLayout(self._mech_box)
        mrow = QtWidgets.QHBoxLayout()
        self.dyn_radio = QtWidgets.QRadioButton(tr("dynamic"))
        self.morph_radio = QtWidgets.QRadioButton(tr("morph"))
        self.dyn_radio.setChecked(True)
        self.mech_group = QtWidgets.QButtonGroup(self)
        self.mech_group.addButton(self.dyn_radio)
        self.mech_group.addButton(self.morph_radio)
        mrow.addWidget(self.dyn_radio)
        mrow.addWidget(self.morph_radio)
        mrow.addStretch(1)
        mrow.addWidget(HelpButton("mechanic"))
        mech_lay.addLayout(mrow)

        mm_row = QtWidgets.QHBoxLayout()
        self._morph_label = self._label("morph_mesh")
        mm_row.addWidget(self._morph_label)
        self.morph_field = _PickField(
            selection.get_selected_mesh, "morph_placeholder")
        mm_row.addWidget(self.morph_field, 1)
        mm_row.addWidget(HelpButton("morph_mesh"))
        mech_lay.addLayout(mm_row)
        root.addWidget(self._mech_box)

        # -- actions ------------------------------------------------------ #
        act_row = QtWidgets.QHBoxLayout()
        act_row.addStretch(1)
        self.validate_btn = QtWidgets.QPushButton(tr("validate"))
        act_row.addWidget(self.validate_btn)
        act_row.addWidget(HelpButton("validate"))
        self.build_btn = QtWidgets.QPushButton(tr("build"))
        act_row.addWidget(self.build_btn)
        act_row.addWidget(HelpButton("build"))
        root.addLayout(act_row)

        # -- wiring ------------------------------------------------------- #
        self.add_btn.clicked.connect(self._add_seam)
        self.rem_btn.clicked.connect(self._remove_seam)
        self.validate_btn.clicked.connect(self._on_validate)
        self.build_btn.clicked.connect(self._on_build)
        self.morph_radio.toggled.connect(self._on_mechanic_changed)
        self._on_mechanic_changed()

    def _add_grid_row(self, grid, r, label_key, widget):
        grid.addWidget(self._label(label_key), r, 0)
        grid.addWidget(widget, r, 1)
        grid.addWidget(HelpButton(label_key), r, 2)

    # ------------------------------------------------------------------ #
    # language
    # ------------------------------------------------------------------ #
    def _on_language_changed(self, idx):
        set_language(_LANGS[idx] if 0 <= idx < len(_LANGS) else "en")
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(tr("win_title"))
        for key, lbl in self._labels.items():
            lbl.setText(tr(key))
        self._seams_box.setTitle(tr("seams"))
        self.add_btn.setText(tr("add_seam"))
        self.rem_btn.setText(tr("remove_seam"))
        # direction combo: keep index, refresh display text
        di = self.dir_combo.currentIndex()
        self.dir_combo.blockSignals(True)
        for i, k in enumerate(_DIR_KEYS):
            self.dir_combo.setItemText(i, tr(k))
        self.dir_combo.setCurrentIndex(di)
        self.dir_combo.blockSignals(False)
        self.invert_chk.setText(tr("invert_wipe"))
        self.final_field.retranslate()
        self.ctrl_field.retranslate()
        self.morph_field.retranslate()
        self._mech_box.setTitle(tr("mechanic"))
        self.dyn_radio.setText(tr("dynamic"))
        self.morph_radio.setText(tr("morph"))
        self.validate_btn.setText(tr("validate"))
        self.build_btn.setText(tr("build"))
        for _item, row in self._seam_rows:
            row.retranslate()

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
        for new_idx, (_it, row) in enumerate(self._seam_rows):
            row.set_title(new_idx)
        self._reclamp_pair_count()

    def _on_mechanic_changed(self, *_):
        is_morph = self.morph_radio.isChecked()
        self.morph_field.setEnabled(is_morph)
        self._morph_label.setEnabled(is_morph)

    # ------------------------------------------------------------------ #
    # dynamic pair-count clamp
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
        direction = _DIRS[self.dir_combo.currentIndex()]
        seams = []
        for _item, row in self._seam_rows:
            ra, rb = row.rails_spec()
            seams.append({
                "rail_a": ra,
                "rail_b": rb,
                "pair_count": self.pair_spin.value(),
                "feather": self.feather_spin.value(),
                "direction": direction,
                "invert": self.invert_chk.isChecked(),
                "controller": self.ctrl_field.text(),
            })
        return {
            "name": self.name_edit.text().strip() or "zipperRig",
            "final_mesh": self.final_field.text(),
            "mechanic": mechanic,
            "morph_mesh": self.morph_field.text() if mechanic == "morph" else "",
            "seams": seams,
        }

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
                self, tr("msg_validate"), tr("msg_validate_ok"))
        else:
            QtWidgets.QMessageBox.warning(
                self, tr("msg_validate"),
                "\n".join(report.errors) or tr("msg_see_rows"))

    def _on_build(self):
        from ..build import zipper_builder
        from ..build.validate import validate
        spec = self._collect_spec()
        report = self._apply_report(validate(spec))
        if not report.ok:
            QtWidgets.QMessageBox.warning(
                self, tr("msg_build"), tr("msg_fix_first"))
            return
        try:
            root = zipper_builder.build(spec, validate_first=False)
        except Exception as exc:                       # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, tr("msg_build_failed"), str(exc))
            return
        QtWidgets.QMessageBox.information(
            self, tr("msg_build"), tr("msg_build_done").format(root))


def show():
    """Create (or re-show) the Zipper System panel, parented to Maya."""
    parent = qt.main_maya_window()
    try:
        globals()["_INSTANCE"].close()
        globals()["_INSTANCE"].deleteLater()
    except Exception:
        pass
    widget = ZipperWidget(parent)
    widget.show()
    globals()["_INSTANCE"] = widget
    return widget
