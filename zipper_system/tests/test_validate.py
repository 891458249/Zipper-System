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
    `attrs` maps a node name -> {attr_name: attr_type} for attributeQuery (used
    by the zip_attr checks); such nodes also report as existing.
    """

    def __init__(self, paths, attrs=None):
        self._paths = paths
        self._attrs = attrs or {}

    def objExists(self, name):
        return name in self._paths or name in self._attrs

    def ls(self, name=None, selection=False, dag=False, type=None,
           noIntermediate=False, long=False, flatten=False):
        if name is None:
            return []
        if dag and type == "nurbsCurve":
            return [self._paths[name]] if name in self._paths else []
        if long:
            return [self._paths[name]] if name in self._paths else []
        return []

    def attributeQuery(self, attr, node=None, exists=False,
                       attributeType=False):
        node_attrs = self._attrs.get(node, {})
        if exists:
            return attr in node_attrs
        if attributeType:
            return node_attrs.get(attr)
        return None


def _spec(mid, rails):
    return {"seams": [{"mid": mid, "rails": list(rails),
                       "direction": "both"}]}


def _run(monkeypatch, paths, spec, attrs=None):
    monkeypatch.setattr(validate, "cmds", _FakeCmds(paths, attrs))
    return validate.validate(spec)


def _ctrl_spec(zip_attr, controller="ctrl"):
    """A valid mid + 2 rails seam carrying a controller and zip_attr, so the
    only thing under test is the zip_attr validation."""
    return {"seams": [{
        "mid": "mid", "rails": ["railA", "railB"], "direction": "both",
        "controller": controller, "zip_attr": zip_attr,
    }]}


_CTRL_PATHS = {
    "mid": "|grp|mid|midShape",
    "railA": "|grp|railA|railAShape",
    "railB": "|grp|railB|railBShape",
}


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


# -- zip_attr (custom zip attribute name) ----------------------------------- #
def test_zip_attr_valid_name_pass(monkeypatch):
    # Controller exists, attr not yet present -> accepted (build will create it).
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec("mouthZip"),
                  attrs={"ctrl": {}})
    assert report.ok


def test_zip_attr_default_when_blank(monkeypatch):
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec(""), attrs={"ctrl": {}})
    assert report.ok


def test_zip_attr_invalid_leading_digit(monkeypatch):
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec("1bad"),
                  attrs={"ctrl": {}})
    assert not report.ok
    assert any("not a valid attribute identifier" in m
               for m in report.seam_errors.get(0, []))


def test_zip_attr_invalid_space(monkeypatch):
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec("a b"),
                  attrs={"ctrl": {}})
    assert not report.ok
    assert any("not a valid attribute identifier" in m
               for m in report.seam_errors.get(0, []))


def test_zip_attr_existing_non_numeric_rejected(monkeypatch):
    # 'zip' already on the controller as a message attr -> not connectable.
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec("zip"),
                  attrs={"ctrl": {"zip": "message"}})
    assert not report.ok
    assert any("not a numeric zip attribute" in m
               for m in report.seam_errors.get(0, []))


def test_zip_attr_existing_numeric_pass(monkeypatch):
    report = _run(monkeypatch, _CTRL_PATHS, _ctrl_spec("zip"),
                  attrs={"ctrl": {"zip": "double"}})
    assert report.ok
