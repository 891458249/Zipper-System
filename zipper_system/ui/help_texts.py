# -*- coding: utf-8 -*-
"""Detailed per-control help texts (English / Chinese).

Each UI control has a help key; ``get_help_text(key)`` returns the description in
the current UI language. Shown by the HelpButton "?" bubble next to each control.
All values are unicode (py2-safe). Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function

from .i18n import current_language


_EN = {
    "rig_name":
        u"Name of the zipper rig. A top group '<name>_zipperRig' is created to "
        u"hold all the nodes built for this rig.",
    "seams":
        u"A Seam is one pair of rails (Rail A + Rail B) that get stitched along "
        u"their shared midline. Add as many seams as you need -- one for a "
        u"normal mouth, several for a 4/5-petal monster mouth. Seams are fully "
        u"independent (own controller / wipe).",
    "add_seam":
        u"Add another independent seam (rail pair) to this rig. There is no "
        u"hard-coded upper/lower assumption -- any two corresponding rails work.",
    "remove_seam":
        u"Remove the currently selected seam row from the list (at least one "
        u"seam is always kept).",
    "rail_a":
        u"The first rail of this seam. Choose the source type (Edge or Curve) "
        u"with the dropdown, then press '<' to capture the current selection:\n"
        u"  Edge  - select a single connected edge loop/path on ONE mesh.\n"
        u"  Curve - select one NURBS curve.\n"
        u"Rails may mix types (e.g. Rail A = edge, Rail B = curve).",
    "rail_b":
        u"The second rail of this seam, paired against Rail A. Same Edge/Curve "
        u"choice as Rail A. The two rails are sampled by arc length and paired "
        u"corner-to-corner, so they need NOT have the same vertex count.",
    "pair_count":
        u"Sampling density N along each rail. Both rails are resampled to N "
        u"evenly arc-length-spaced points and paired (a_k, b_k). Higher = finer "
        u"seal but more work. Auto-clamped to the rail's vertex limit.",
    "feather":
        u"Wipe feather band (beta). Width of the soft transition as each pair "
        u"closes: 0 = hard on/off step, larger = softer, more gradual seal "
        u"around the moving zip front.",
    "direction":
        u"Order in which pairs close as the controller's zip goes 0 -> 1:\n"
        u"  both - both ends seal first, meeting at the centre (default).\n"
        u"  ltr  - sweeps from the left corner to the right.\n"
        u"  rtl  - sweeps from the right corner to the left.",
    "invert_wipe":
        u"Reverse the closing order. With 'both' this flips ends->centre into "
        u"centre->ends. (Resolves the blueprint sec.3.3 ambiguity by exposing "
        u"both directions; default off = ends->centre.)",
    "final_mesh":
        u"The mesh that actually gets DEFORMED (e.g. the head). The rails are "
        u"only drivers that define the seam path; the seam vertices of THIS "
        u"mesh nearest each sampled pair are driven toward the midline.\n\n"
        u"The target geometry. The checkbox toggles two rig types:\n"
        u"  CHECKED = Final Mesh: the picked mesh deforms toward the rails' live "
        u"midline (the rails drive the mesh).\n"
        u"  UNCHECKED = Final Curve: rail A and rail B deform ONTO this curve -- "
        u"the curve is the seam line they zip onto, reaching it exactly at "
        u"zip = 1. Rails may be curves (their CVs) or edges (the mesh verts). "
        u"For an edge rail the mesh is auto-inferred. Press '<' with the "
        u"mesh/curve selected.",
    "controller":
        u"The control object whose 'zip' attribute (0..1) drives this seam's "
        u"closure. If it has no 'zip' attribute one is added automatically and "
        u"connected. Press '<' with the controller selected.",
    "mechanic":
        u"Closure mechanic:\n"
        u"  Dynamic midline - a live deformer recomputes the midline every "
        u"frame, so the seal follows the mouth (sticky-lips feel). Exact wipe "
        u"order.\n"
        u"  Morph - a blendShape cross-fades to a pre-sculpted closed shape, "
        u"driven by the controller. O(1) nodes per seam, GPU-friendly; the "
        u"performance stand-in (uniform close, no per-pair wipe order).",
    "morph_mesh":
        u"Only for the Morph mechanic: a pre-sculpted 'already closed' copy of "
        u"the final mesh (same topology / vertex count). The blendShape fades "
        u"the final mesh toward this shape as the controller drives the close.",
    "validate":
        u"Run all pre-build checks WITHOUT creating anything: node existence, "
        u"edges form a single chain on one object, pair-count range, mechanic "
        u"field rules. Offending seam rows are highlighted. Zero side effects.",
    "build":
        u"Validate, then build the rig inside a single undo chunk with a "
        u"progress bar. Any error rolls the whole thing back -- no orphan "
        u"nodes left behind.",
    "language":
        u"Switch the interface language between English and Chinese. The choice "
        u"is remembered across Maya sessions.",
}

_ZH = {
    "rig_name":
        u"拉链绑定的名称。会创建一个顶层组 '<名称>_zipperRig' 来容纳本次构建的所有节点。",
    "seams":
        u"一条「缝 (Seam)」= 一对轨（轨 A + 轨 B），沿它们的中线缝合。需要几条就加几条："
        u"普通嘴 1 条，4/5 瓣怪物嘴用多条。各缝完全独立（各自的控制器 / wipe），代码不写死上下唇。",
    "add_seam":
        u"为本绑定新增一条独立的缝（轨对）。不预设上/下唇——任意两条相对应的轨都可以。",
    "remove_seam":
        u"从列表中删除当前选中的缝行（至少保留一条缝）。",
    "rail_a":
        u"本缝的第一条轨。用下拉框选择来源类型（边 / 曲线），再点 '<' 拾取当前选择：\n"
        u"  边   —— 在同一个网格上选一条相连的边环 / 边链。\n"
        u"  曲线 —— 选一条 NURBS 曲线。\n"
        u"两条轨可混用类型（如 轨 A 用边、轨 B 用曲线）。",
    "rail_b":
        u"本缝的第二条轨，与轨 A 配对。Edge/Curve 选择同轨 A。两条轨按弧长重采样并端到端配对，"
        u"因此两轨顶点数可以不相等。",
    "pair_count":
        u"沿每条轨的采样密度 N。两条轨各重采样为 N 个按弧长均匀分布的点并配对 (a_k, b_k)。"
        u"越大缝合越细但开销越大。会自动钳制到轨的顶点上限。",
    "feather":
        u"Wipe 羽化带宽 (beta)。每一对闭合时柔性过渡的宽度：0 = 硬性开关，越大越柔和、"
        u"拉链推进的前沿越平滑。",
    "direction":
        u"控制器 zip 从 0→1 时各对的闭合顺序：\n"
        u"  双向 —— 两端先合、于中央会合（默认）。\n"
        u"  左→右 —— 从左侧角扫到右侧。\n"
        u"  右→左 —— 从右侧角扫到左侧。",
    "invert_wipe":
        u"反转闭合顺序。在「双向」下，把「两端→中央」翻成「中央→两端」。"
        u"（蓝图 §3.3 公式与文字相互矛盾，这里两种方向都暴露；默认关闭 = 两端→中央。）",
    "final_mesh":
        u"真正被「变形」的网格（如头部）。轨只是定义缝路径的驱动；会在「这个网格」上"
        u"找到离每个采样对最近的缝顶点，把它们拉向中线。\n\n"
        u"目标几何体。勾选框切换两种绑定类型：\n"
        u"  勾选 = 最终网格：所选网格向两轨的实时中线变形（轨驱动网格）。\n"
        u"  取消 = 最终曲线：轨 A 和轨 B 变形「贴合」到这条曲线——曲线就是它们要拉合到的缝线，"
        u"zip = 1 时精确贴合。轨可以是曲线（变其 CV）或边（变网格顶点）；边轨会自动推断网格。"
        u"选中网格/曲线后点 '<'。",
    "controller":
        u"驱动本缝闭合的控制器，其 'zip' 属性 (0..1) 控制闭合量。若没有 'zip' 属性会自动添加并连接。"
        u"选中控制器后点 '<'。",
    "mechanic":
        u"闭合机制：\n"
        u"  动态中线 —— 实时 deformer 每帧重算中线，密封线跟随嘴部运动（sticky-lips 手感），"
        u"精确的 wipe 顺序。\n"
        u"  静态 Morph —— 用 blendShape 交叉淡化到预雕的「已闭合」形状，由控制器驱动。"
        u"每缝 O(1) 节点、GPU 友好；性能替身（均匀闭合，无逐对 wipe 顺序）。",
    "morph_mesh":
        u"仅用于 Morph 机制：预雕好的「已闭合」最终网格副本（拓扑 / 顶点数相同）。"
        u"控制器驱动闭合时，blendShape 把最终网格淡化到此形状。",
    "validate":
        u"在「不创建任何节点」的前提下跑全部预校验：节点存在性、边是否在同一物体上排成单链、"
        u"采样对数范围、机制字段规则。非法的缝行会高亮。零副作用。",
    "build":
        u"先校验，再在单个 undo 块内带进度条构建绑定。任何错误都会整体回滚——不残留孤立节点。",
    "language":
        u"在中文与英文之间切换界面语言。该选择会跨 Maya 会话记住。",
}

_TABLES = {"en": _EN, "zh": _ZH}


def get_help_text(key):
    """Return the help text for *key* in the current UI language."""
    table = _TABLES.get(current_language(), _EN)
    return table.get(key, _EN.get(key, u""))
