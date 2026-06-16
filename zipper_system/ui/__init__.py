# -*- coding: utf-8 -*-
"""UI layer -- PySide2/6 panels. Depends only on build/core, always via the
compat shim (never imports PySide directly). (ARCHITECTURE.md sec.4 / sec.6)
"""
from __future__ import absolute_import, division, print_function


from .zipper_widget import ZipperWidget  # noqa: F401
from .main_window import ZipperMainWindow, show  # noqa: F401
