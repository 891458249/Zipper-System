# -*- coding: utf-8 -*-
"""Core domain layer -- pure logic, no cmds / no Qt (ARCHITECTURE.md sec.4).

om2 is used only inside the concrete rail classes for data access, and is
imported lazily so this package stays importable (and unit-testable) without a
running Maya.
"""
from __future__ import absolute_import, division, print_function


from . import math_util       # noqa: F401
from . import sampling        # noqa: F401
from .rail import RailData, RailSource, from_spec  # noqa: F401
from .rail_edge import order_edge_chain, EdgeOrderError  # noqa: F401
from .seam import Seam        # noqa: F401
