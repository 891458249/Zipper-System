# -*- coding: utf-8 -*-
"""Tiny Python 2/3 compatibility helpers (Maya 2022.5.1 may run mayapy2).

Pure stdlib, no Maya/Qt. The key need: in Maya's Python-2 mode, ``cmds`` returns
``unicode`` node names, so a plain ``isinstance(x, str)`` check fails. Use
``string_types`` for any "is this a node-name string?" test.
"""
from __future__ import absolute_import, division, print_function

import sys

if sys.version_info[0] >= 3:
    string_types = (str,)
    text_type = str
else:  # pragma: no cover - exercised only under mayapy2
    string_types = (str, unicode)  # noqa: F821
    text_type = unicode            # noqa: F821
