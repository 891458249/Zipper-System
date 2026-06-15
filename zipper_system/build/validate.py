# -*- coding: utf-8 -*-
"""Pre-build validation (curve-only).

A seam is three NURBS curves: rail_a, mid, rail_b. Build is refused unless every
curve exists and is a NURBS curve, so a failed validation has ZERO side effects.
The same checks back the UI's Validate button (it highlights bad seam rows).
"""
from __future__ import absolute_import, division, print_function

from maya import cmds

from ..core._compat import string_types

VALID_DIRECTIONS = ("both", "ltr", "rtl")


class ValidationReport(object):
    """Outcome of validating a rig_spec.

    ok          : bool, True iff no errors.
    errors      : list of global error strings.
    seam_errors : dict {seam_index: [error strings]} for UI row highlighting.
    """

    def __init__(self):
        self.errors = []
        self.seam_errors = {}

    @property
    def ok(self):
        return not self.errors and not any(self.seam_errors.values())

    def add(self, msg):
        self.errors.append(msg)

    def add_seam(self, idx, msg):
        self.seam_errors.setdefault(idx, []).append(msg)

    def __repr__(self):
        return "ValidationReport(ok=%s, errors=%d)" % (
            self.ok, len(self.errors) + sum(
                len(v) for v in self.seam_errors.values()))


def _obj_exists(name):
    return bool(name) and cmds.objExists(name)


def _is_curve(name):
    if not _obj_exists(name):
        return False
    return bool(cmds.ls(name, dag=True, type="nurbsCurve", noIntermediate=True))


def _canonical(name):
    """Return a unique identity for a curve handle: its shape's full DAG path.

    Two handles that point at the same object (e.g. mid picked as rail_a, or a
    short-name collision) yield the same value, which lets the seam distinctness
    check below catch a degenerate seam. Returns None if it cannot be resolved.
    """
    shapes = cmds.ls(name, dag=True, type="nurbsCurve",
                     noIntermediate=True, long=True)
    if shapes:
        return shapes[0]
    full = cmds.ls(name, long=True)
    return full[0] if full else None


def _check_curve(report, idx, label, handle):
    name = handle if isinstance(handle, string_types) else None
    if not name:
        report.add_seam(idx, "%s: nothing picked" % label)
    elif not _is_curve(name):
        report.add_seam(idx, "%s: %r is not a NURBS curve" % (label, name))


def validate(rig_spec):
    # type: (dict) -> ValidationReport
    """Validate a curve-only rig_spec; never mutates the scene."""
    report = ValidationReport()
    if not isinstance(rig_spec, dict):
        report.add("rig_spec must be a dict")
        return report

    seams = rig_spec.get("seams")
    if not seams:
        report.add("add at least one seam")
        return report

    for idx, seam in enumerate(seams):
        if not isinstance(seam, dict):
            report.add_seam(idx, "seam must be a dict")
            continue
        _check_curve(report, idx, "rail_a", seam.get("rail_a"))
        _check_curve(report, idx, "mid", seam.get("mid"))
        _check_curve(report, idx, "rail_b", seam.get("rail_b"))

        # rail_a / mid / rail_b must be three distinct curves; if mid resolves to
        # the same object as a rail (mis-pick or short-name collision) the rig
        # silently builds wrong (a rail conforms to itself), so reject it here.
        # Only compare handles that already resolved to curves -- a missing /
        # non-curve handle is reported above and not re-flagged.
        resolved = {}
        for label in ("rail_a", "mid", "rail_b"):
            handle = seam.get(label)
            if isinstance(handle, string_types) and _is_curve(handle):
                resolved[label] = _canonical(handle)
        labels = list(resolved)
        clashed = False
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                a, b = resolved[labels[i]], resolved[labels[j]]
                if a is not None and a == b:
                    clashed = True
        if clashed:
            report.add_seam(
                idx,
                "rail_a / mid / rail_b must be three distinct curves "
                "(mid cannot be the same object as a rail)")

        direction = seam.get("direction", "both")
        if direction not in VALID_DIRECTIONS:
            report.add_seam(idx, "direction must be %r, got %r"
                            % (VALID_DIRECTIONS, direction))

        controller = seam.get("controller")
        if controller and not _obj_exists(controller):
            report.add_seam(idx, "controller %r does not exist" % (controller,))

    return report
