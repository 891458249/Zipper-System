# -*- coding: utf-8 -*-
"""'?' help button + floating help bubble (adapted from the RBFtools pattern).

A small round "?" QToolButton sits next to each control. Hovering shows a
floating bubble with the control's help text in the current UI language; clicking
pins the bubble so it stays while you read. The bubble always re-fetches text via
``get_help_text`` at show time, so it follows the language switch automatically.

All Qt access goes through the compat shim (PySide2/6). Python 2.7 / 3.x safe.
"""
from __future__ import absolute_import, division, print_function

from ..compat import qtcompat as qt

QtCore = qt.QtCore
QtWidgets = qt.QtWidgets


class HelpBubble(QtWidgets.QWidget):
    """A frameless floating tooltip-like bubble."""

    def __init__(self, parent=None):
        flags = (QtCore.Qt.Tool
                 | QtCore.Qt.FramelessWindowHint
                 | QtCore.Qt.WindowStaysOnTopHint)
        super(HelpBubble, self).__init__(parent, flags)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "HelpBubble {"
            "  background: #2b2b2b;"
            "  border: 1px solid #555;"
            "  border-radius: 6px;"
            "}"
            "QLabel { color: #ddd; font-size: 12px; background: transparent; }"
        )
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self._label = QtWidgets.QLabel()
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(320)
        lay.addWidget(self._label)

    def set_text(self, text):
        self._label.setText(text)
        self.adjustSize()

    def reposition(self, anchor_global_pos):
        self.move(anchor_global_pos.x() + 20, anchor_global_pos.y() - 10)


class HelpButton(QtWidgets.QToolButton):
    """Small round '?' button showing a help bubble for ``help_key``."""

    _active_pinned = None  # only one pinned bubble at a time

    def __init__(self, help_key, parent=None):
        super(HelpButton, self).__init__(parent)
        self._help_key = help_key
        self._pinned = False
        self._bubble = None
        self._win = None

        self.setText("?")
        self.setFixedSize(18, 18)
        self.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid #666; border-radius: 9px;"
            "  background: #3a3a3a; color: #bbb;"
            "  font-size: 11px; font-weight: bold;"
            "}"
            "QToolButton:hover {"
            "  background: #505050; color: #fff; border-color: #888;"
            "}"
        )
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.clicked.connect(self._on_click)

    # -- bubble plumbing ---------------------------------------------------- #
    def _get_bubble(self):
        if self._bubble is None:
            self._bubble = HelpBubble()
        return self._bubble

    def _help_text(self):
        from .help_texts import get_help_text
        return get_help_text(self._help_key)

    def _anchor(self):
        return self.mapToGlobal(QtCore.QPoint(self.width(), 0))

    def _show_bubble(self):
        bubble = self._get_bubble()
        bubble.set_text(self._help_text())
        bubble.reposition(self._anchor())
        bubble.show()

    def _hide_bubble(self):
        if self._bubble is not None:
            self._bubble.hide()

    def _top_window(self):
        if self._win is None:
            self._win = self.window()
        return self._win

    # -- interaction -------------------------------------------------------- #
    def _on_click(self):
        if self._pinned:
            self._pinned = False
            self._hide_bubble()
            self._uninstall_filter()
            if HelpButton._active_pinned is self:
                HelpButton._active_pinned = None
        else:
            other = HelpButton._active_pinned
            if other is not None and other is not self:
                other._on_click()
            self._pinned = True
            HelpButton._active_pinned = self
            self._show_bubble()
            self._install_filter()

    def _install_filter(self):
        win = self._top_window()
        if win is not None:
            win.installEventFilter(self)

    def _uninstall_filter(self):
        win = self._top_window()
        if win is not None:
            try:
                win.removeEventFilter(self)
            except (TypeError, RuntimeError):
                pass

    def eventFilter(self, obj, event):
        et = event.type()
        if et in (QtCore.QEvent.Move, QtCore.QEvent.Resize):
            if self._pinned and self._bubble and self._bubble.isVisible():
                self._bubble.reposition(self._anchor())
        elif et in (QtCore.QEvent.WindowStateChange, QtCore.QEvent.Hide):
            if self._pinned and self._bubble and self._bubble.isVisible():
                self._on_click()
        return False

    def enterEvent(self, event):
        if not self._pinned:
            self._show_bubble()
        super(HelpButton, self).enterEvent(event)

    def leaveEvent(self, event):
        if not self._pinned:
            self._hide_bubble()
        super(HelpButton, self).leaveEvent(event)

    def hideEvent(self, event):
        if self._pinned:
            self._pinned = False
            if HelpButton._active_pinned is self:
                HelpButton._active_pinned = None
            self._uninstall_filter()
        self._hide_bubble()
        super(HelpButton, self).hideEvent(event)
