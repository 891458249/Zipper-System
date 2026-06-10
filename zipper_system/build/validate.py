# -*- coding: utf-8 -*-
"""Pre-build validation (ARCHITECTURE.md sec.8).

Build is refused unless every input is legal, so a failed validation has ZERO
side effects (no nodes created). The same checks back the UI's standalone
``Validate`` button, which highlights the offending seam rows.

This layer may use cmds + om2; the edge-orderability check reuses the pure
``core`` algorithm.
"""

# Python 3.7-common syntax only.

from maya import cmds

from ..core.rail_edge import order_edge_chain, EdgeOrderError

MAX_CURVE_SAMPLES = 400  # soft cap for curve rails (edges cap at vertex count)
VALID_MECHANICS = ("dynamic", "morph")
VALID_DIRECTIONS = ("both", "ltr", "rtl")


class ValidationReport(object):
    """Outcome of validating a rig_spec.

    ok          : bool, True iff no errors.
    errors      : list of global error strings.
    seam_errors : dict {seam_index: [error strings]} for UI row highlighting.
    seam_caps   : dict {seam_index: pair_count upper bound} (min over rails).
    """

    def __init__(self):
        self.errors = []
        self.seam_errors = {}
        self.seam_caps = {}

    @property
    def ok(self):
        return not self.errors and not any(self.seam_errors.values())

    def add(self, msg):
        self.errors.append(msg)

    def add_seam(self, idx, msg):
        self.seam_errors.setdefault(idx, []).append(msg)

    def __repr__(self):
        return "ValidationReport(ok=%s, errors=%d, seam_errors=%d)" % (
            self.ok, len(self.errors),
            sum(len(v) for v in self.seam_errors.values()))


def _obj_exists(name):
    return bool(name) and cmds.objExists(name)


def _is_mesh(name):
    if not _obj_exists(name):
        return False
    shapes = cmds.ls(name, dag=True, type="mesh", noIntermediate=True)
    return bool(shapes)


def _vertex_count(mesh):
    try:
        return cmds.polyEvaluate(mesh, vertex=True)
    except Exception:
        return None


def _edge_handle_to_pairs(handle):
    """Resolve an edge rail handle into (vertex_pair_list, mesh_name).

    handle: list of 'mesh.e[i]' strings, or (mesh_name, [edge_ids]).
    Returns (pairs, mesh) or raises ValueError / EdgeOrderError.
    """
    from maya.api import OpenMaya as om
    if isinstance(handle, (list, tuple)) and len(handle) == 2 \
            and isinstance(handle[0], str) \
            and isinstance(handle[1], (list, tuple)):
        mesh = handle[0]
        edge_ids = list(handle[1])
        sel = om.MSelectionList()
        sel.add(mesh)
        dag = sel.getDagPath(0)
    else:
        if not handle:
            raise ValueError("empty edge selection")
        sel = om.MSelectionList()
        mesh = None
        edge_ids = []
        for s in handle:
            sel.add(s)
        for i in range(sel.length()):
            d, comp = sel.getComponent(i)
            if mesh is None:
                mesh = d.fullPathName()
                dag = d
            elif d.fullPathName() != mesh:
                raise ValueError(
                    "edges span multiple objects (%s vs %s)"
                    % (mesh, d.fullPathName()))
            if comp.isNull():
                raise ValueError("%r is not an edge component" % (s,))
            edge_ids.extend(om.MFnSingleIndexedComponent(comp).getElements())
    edge_iter = om.MItMeshEdge(dag)
    pairs = []
    for eid in edge_ids:
        edge_iter.setIndex(eid)
        pairs.append((edge_iter.vertexId(0), edge_iter.vertexId(1)))
    return pairs, mesh


def _validate_rail(report, idx, label, rail_spec):
    """Validate one rail spec; return its pair_count cap or None on error."""
    if not isinstance(rail_spec, dict):
        report.add_seam(idx, "%s: rail spec must be a dict" % label)
        return None
    rtype = rail_spec.get("type")
    handle = rail_spec.get("handle")
    if rtype not in ("edge", "curve"):
        report.add_seam(idx, "%s: type must be 'edge'|'curve', got %r"
                        % (label, rtype))
        return None
    if not handle:
        report.add_seam(idx, "%s: empty handle" % label)
        return None

    if rtype == "edge":
        try:
            pairs, mesh = _edge_handle_to_pairs(handle)
            ordered, _closed = order_edge_chain(pairs)
        except (EdgeOrderError, ValueError) as exc:
            report.add_seam(idx, "%s: %s" % (label, exc))
            return None
        except RuntimeError as exc:
            report.add_seam(idx, "%s: cannot resolve edges (%s)" % (label, exc))
            return None
        return len(ordered)

    # curve
    name = handle if isinstance(handle, str) else None
    if name is None or not _obj_exists(name):
        report.add_seam(idx, "%s: curve %r does not exist" % (label, handle))
        return None
    is_curve = bool(cmds.ls(name, dag=True, type="nurbsCurve"))
    if not is_curve:
        report.add_seam(idx, "%s: %r is not a NURBS curve" % (label, name))
        return None
    return MAX_CURVE_SAMPLES


def rail_cap(rail_spec):
    # type: (dict) -> int
    """Return the pair_count upper bound for one rail spec, or None if the rail
    cannot be resolved. Used by the UI to clamp the Pair Count field (sec.6).
    """
    if not isinstance(rail_spec, dict):
        return None
    rtype = rail_spec.get("type")
    handle = rail_spec.get("handle")
    if not handle:
        return None
    if rtype == "edge":
        try:
            pairs, _mesh = _edge_handle_to_pairs(handle)
            ordered, _closed = order_edge_chain(pairs)
            return len(ordered)
        except (EdgeOrderError, ValueError, RuntimeError):
            return None
    if rtype == "curve":
        name = handle if isinstance(handle, str) else None
        if name and cmds.ls(name, dag=True, type="nurbsCurve"):
            return MAX_CURVE_SAMPLES
        return None
    return None


def seam_cap(seam_spec):
    # type: (dict) -> int
    """Min pair_count cap across a seam's two rails, or None if unresolved."""
    ca = rail_cap(seam_spec.get("rail_a", {}))
    cb = rail_cap(seam_spec.get("rail_b", {}))
    if ca is None or cb is None:
        return None
    return min(ca, cb)


def validate(rig_spec):
    # type: (dict) -> ValidationReport
    """Validate a rig_spec; never mutates the scene."""
    report = ValidationReport()
    if not isinstance(rig_spec, dict):
        report.add("rig_spec must be a dict")
        return report

    mechanic = rig_spec.get("mechanic")
    if mechanic not in VALID_MECHANICS:
        report.add("mechanic must be 'dynamic'|'morph', got %r" % (mechanic,))

    final_mesh = rig_spec.get("final_mesh")
    if not _is_mesh(final_mesh):
        report.add("final_mesh %r does not exist or is not a mesh"
                   % (final_mesh,))

    morph_mesh = rig_spec.get("morph_mesh")
    if mechanic == "morph":
        if not _is_mesh(morph_mesh):
            report.add("morph mechanic requires a valid morph_mesh (got %r)"
                       % (morph_mesh,))
        elif _is_mesh(final_mesh):
            if _vertex_count(morph_mesh) != _vertex_count(final_mesh):
                report.add("morph_mesh and final_mesh vertex counts differ "
                           "(blendShape requires matching topology)")
    elif mechanic == "dynamic":
        # sec.8: dynamic mode forbids morph fields.
        if morph_mesh:
            report.add("dynamic mechanic must not set morph_mesh (got %r)"
                       % (morph_mesh,))

    seams = rig_spec.get("seams")
    if not seams:
        report.add("rig_spec must contain at least one seam")
        seams = []

    for idx, seam in enumerate(seams):
        if not isinstance(seam, dict):
            report.add_seam(idx, "seam must be a dict")
            continue
        cap_a = _validate_rail(report, idx, "rail_a", seam.get("rail_a", {}))
        cap_b = _validate_rail(report, idx, "rail_b", seam.get("rail_b", {}))

        direction = seam.get("direction", "both")
        if direction not in VALID_DIRECTIONS:
            report.add_seam(idx, "direction must be %r, got %r"
                            % (VALID_DIRECTIONS, direction))

        controller = seam.get("controller")
        if controller and not _obj_exists(controller):
            report.add_seam(idx, "controller %r does not exist" % (controller,))

        pair_count = seam.get("pair_count", 30)
        cap = None
        if cap_a is not None and cap_b is not None:
            cap = min(cap_a, cap_b)
            report.seam_caps[idx] = cap
        try:
            pc = int(pair_count)
        except (TypeError, ValueError):
            report.add_seam(idx, "pair_count must be an int, got %r"
                            % (pair_count,))
            continue
        if pc < 2:
            report.add_seam(idx, "pair_count must be >= 2, got %d" % pc)
        elif cap is not None and pc > cap:
            report.add_seam(idx, "pair_count %d exceeds rail cap %d" % (pc, cap))

    return report
