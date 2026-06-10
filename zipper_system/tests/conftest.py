# -*- coding: utf-8 -*-
"""Make the repo root importable so `import zipper_system` works under pytest
regardless of the invocation directory.
"""

import os
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
