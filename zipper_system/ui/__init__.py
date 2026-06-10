# -*- coding: utf-8 -*-
"""UI layer -- PySide2/6 panels. Depends only on build/core, always via the
compat shim (never imports PySide directly). (ARCHITECTURE.md sec.4 / sec.6)
"""

from .zipper_widget import ZipperWidget, show  # noqa: F401
