# -*- coding: utf-8 -*-
"""Unit tests for the pure (Maya-free) parts of the rig metadata stamp.

``_seam_controllers`` derives the de-duplicated, order-preserving controller
list stamped onto rig_root.zipperControllers; it touches no cmds, so it is
testable headless. zipper_builder does ``from maya import cmds`` at import time,
so we stub a placeholder maya package first (its attributes are never called by
the pure function under test).
"""
from __future__ import absolute_import, division, print_function

import sys
import types

if "maya" not in sys.modules:
    _maya = types.ModuleType("maya")
    _maya.cmds = types.ModuleType("maya.cmds")
    sys.modules["maya"] = _maya
    sys.modules["maya.cmds"] = _maya.cmds

from zipper_system.build import zipper_builder as zb  # noqa: E402


def test_controllers_dedup_preserves_order():
    seams = [{"controller": "ctrlB"}, {"controller": "ctrlA"},
             {"controller": "ctrlB"}]
    assert zb._seam_controllers(seams) == ["ctrlB", "ctrlA"]


def test_controllers_skips_blank_and_missing():
    seams = [{"controller": ""}, {"controller": "  "}, {},
             {"controller": "ctrlA"}]
    assert zb._seam_controllers(seams) == ["ctrlA"]


def test_controllers_strips_whitespace():
    seams = [{"controller": "  ctrlA  "}]
    assert zb._seam_controllers(seams) == ["ctrlA"]


def test_controllers_empty_when_none():
    assert zb._seam_controllers([{"controller": ""}, {}]) == []
