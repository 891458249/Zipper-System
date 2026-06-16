# -*- coding: utf-8 -*-
"""Unit tests for the curve-only pre-build validation.

validate.py talks to maya.cmds, which is unavailable headless, so we patch its
module-level `cmds` with a tiny fake. The fake maps each curve handle to a
canonical shape path; two handles sharing a path model the bug we guard against
(mid picked as a rail / short-name collision resolving to the same object).
"""
from __future__ import absolute_import, division, print_function

import sys
import types

# validate.py does `from maya import cmds` at import time; stub a placeholder
# maya package so it imports headless. Each test then patches validate.cmds with
# a per-case fake, so this placeholder's attributes are never actually called.
if "maya" not in sys.modules:
    _maya = types.ModuleType("maya")
    _maya.cmds = types.ModuleType("maya.cmds")
    sys.modules["maya"] = _maya
    sys.modules["maya.cmds"] = _maya.cmds

from zipper_system.build import validate  # noqa: E402


class _FakeCmds(object):
    """Minimal maya.cmds stand-in: `paths` maps handle -> canonical shape path.

    A handle present in `paths` exists and is a NURBS curve; everything ls()
    needs (existence, curve test, long/canonical path) is derived from it.
    """

    def __init__(self, paths):
        self._paths = paths

    def objExists(self, name):
        return name in self._paths

    def ls(self, name=None, selection=False, dag=False, type=None,
           noIntermediate=False, long=False, flatten=False):
        if name is None:
            return []
        if dag and type == "nurbsCurve":
            return [self._paths[name]] if name in self._paths else []
        if long:
            return [self._paths[name]] if name in self._paths else []
        return []


def _spec(mid, rails):
    return {"seams": [{"mid": mid, "rails": list(rails),
                       "direction": "both"}]}


def _run(monkeypatch, paths, spec):
    monkeypatch.setattr(validate, "cmds", _FakeCmds(paths))
    return validate.validate(spec)


def test_distinct_curves_pass(monkeypatch):
    paths = {
        "railA": "|grp|railA|railAShape",
        "mid": "|grp|mid|midShape",
        "railB": "|grp|railB|railBShape",
    }
    report = _run(monkeypatch, paths, _spec("mid", ["railA", "railB"]))
    assert report.ok
    assert 0 not in report.seam_errors or not report.seam_errors[0]


def test_variable_rail_count_pass(monkeypatch):
    # N rails (here 3) all distinct from mid and each other: accepted.
    paths = {
        "mid": "|grp|mid|midShape",
        "r0": "|grp|r0|r0Shape",
        "r1": "|grp|r1|r1Shape",
        "r2": "|grp|r2|r2Shape",
    }
    report = _run(monkeypatch, paths, _spec("mid", ["r0", "r1", "r2"]))
    assert report.ok


def test_empty_rails_reports_seam_error(monkeypatch):
    paths = {"mid": "|grp|mid|midShape"}
    report = _run(monkeypatch, paths, _spec("mid", []))
    assert not report.ok
    assert any("at least one rail" in m for m in report.seam_errors.get(0, []))


def test_mid_same_object_as_a_rail_reports_seam_error(monkeypatch):
    # mid and a rail resolve to the SAME canonical shape path: degenerate seam.
    shared = "|grp|railA|railAShape"
    paths = {
        "railA": shared,
        "mid": shared,
        "railB": "|grp|railB|railBShape",
    }
    report = _run(monkeypatch, paths, _spec("mid", ["railA", "railB"]))
    assert not report.ok
    msgs = report.seam_errors.get(0, [])
    assert any("different curve from mid" in m for m in msgs)


def test_two_rails_same_object_reports_seam_error(monkeypatch):
    shared = "|grp|rail|railShape"
    paths = {
        "railA": shared,
        "mid": "|grp|mid|midShape",
        "railB": shared,
    }
    report = _run(monkeypatch, paths, _spec("mid", ["railA", "railB"]))
    assert not report.ok
    assert any("same curve" in m for m in report.seam_errors.get(0, []))
