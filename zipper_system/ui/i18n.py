# -*- coding: utf-8 -*-
"""UI string tables + language switch (English / Chinese).

Mirrors the RBFtools pattern: the current language is persisted in a Maya
optionVar so it survives across sessions; ``tr(key)`` returns the string for the
current language (falling back to English, then the key itself). Widgets fetch
text through ``tr`` and re-fetch in their ``retranslate()`` after a switch.

Import-safe outside Maya (optionVar access is guarded; a process-global holds
the choice when cmds is unavailable). Python 2.7 / 3.x compatible.
"""
from __future__ import absolute_import, division, print_function


_LANG_OPT_VAR = "ZipperSystem_language"
_STATE = {"lang": "en"}  # process fallback when Maya optionVar is unavailable


def current_language():
    """Return 'en' or 'zh'."""
    try:
        from maya import cmds
        if cmds.optionVar(exists=_LANG_OPT_VAR):
            val = cmds.optionVar(query=_LANG_OPT_VAR)
            return val if val in ("en", "zh") else "en"
        return _STATE["lang"]
    except Exception:
        return _STATE["lang"]


def set_language(lang):
    """Persist the language choice ('en' | 'zh')."""
    if lang not in ("en", "zh"):
        lang = "en"
    _STATE["lang"] = lang
    try:
        from maya import cmds
        cmds.optionVar(sv=(_LANG_OPT_VAR, lang))
    except Exception:
        pass


def tr(key):
    """Translate *key* into the current UI language."""
    table = _TABLES.get(current_language(), _EN)
    return table.get(key, _EN.get(key, key))


# --------------------------------------------------------------------------- #
# Label tables (all values are unicode -> py2-safe). '{0}' = format slots.
# --------------------------------------------------------------------------- #
_EN = {
    "win_title": u"Zipper System",
    "language": u"Language",
    "rig_name": u"Rig Name:",
    "seams": u"Seams",
    "add_seam": u"+ Add Seam",
    "remove_seam": u"- Remove",
    "rail_a": u"Rail A:",
    "mid_curve": u"Mid Curve:",
    "rail_b": u"Rail B:",
    "rails": u"Rails",
    "add_rail": u"+",
    "remove_rail": u"-",
    "rail_n": u"Rail {0}:",
    "edge": u"Edge",
    "curve": u"Curve",
    "seam_title": u"Seam {0}",
    "nothing_picked": u"(nothing picked)",
    "pick_tip": u"Capture the current selection",
    "pair_count": u"Pair Count:",
    "feather": u"Feather (beta):",
    "direction": u"Direction:",
    "dir_both": u"both",
    "dir_ltr": u"ltr",
    "dir_rtl": u"rtl",
    "invert_wipe": u"Invert wipe (center -> ends)",
    "requires_plugin": u"Downstream needs plugin",
    "final_mesh": u"Final Mesh:",
    "final_curve": u"Final Curve:",
    "final_auto": u"(auto from edges, or pick the mesh)",
    "controller": u"Controller:",
    "controller_attr": u"Zip Attribute",
    "mechanic": u"Mechanic",
    "dynamic": u"Dynamic midline",
    "morph": u"Morph",
    "morph_mesh": u"Morph Mesh:",
    "morph_curve": u"Morph Curve:",
    "morph_placeholder": u"(Morph mode only)",
    "validate": u"Validate",
    "build": u"Build",
    "msg_validate": u"Validate",
    "msg_validate_ok": u"Validation passed.",
    "msg_see_rows": u"See the highlighted seam rows.",
    "msg_build": u"Build",
    "msg_fix_first": u"Fix the validation errors first.",
    "msg_build_done": u"Built rig: {0}",
    "msg_build_failed": u"Build failed",
    "edges_count": u"{0} edge(s) on {1}",
    "pick_warn": u"Pick",
}

_ZH = {
    "win_title": u"拉链缝合系统",
    "language": u"语言",
    "rig_name": u"绑定名称：",
    "seams": u"缝 (Seams)",
    "add_seam": u"+ 添加缝",
    "remove_seam": u"- 删除",
    "rail_a": u"轨 A：",
    "mid_curve": u"中间曲线：",
    "rail_b": u"轨 B：",
    "rails": u"轨 (Rails)",
    "add_rail": u"加轨",
    "remove_rail": u"删轨",
    "rail_n": u"轨 {0}：",
    "edge": u"边",
    "curve": u"曲线",
    "seam_title": u"缝 {0}",
    "nothing_picked": u"（未拾取）",
    "pick_tip": u"拾取当前选择",
    "pair_count": u"采样对数：",
    "feather": u"羽化 (beta)：",
    "direction": u"方向：",
    "dir_both": u"双向",
    "dir_ltr": u"左→右",
    "dir_rtl": u"右→左",
    "invert_wipe": u"反转拉合方向（中央→两端）",
    "requires_plugin": u"下游需要安装插件",
    "final_mesh": u"最终网格：",
    "final_curve": u"最终曲线：",
    "final_auto": u"（边模式自动推断，或拾取网格）",
    "controller": u"控制器：",
    "controller_attr": u"Zip 属性名",
    "mechanic": u"闭合机制",
    "dynamic": u"动态中线",
    "morph": u"静态 Morph",
    "morph_mesh": u"Morph 网格：",
    "morph_curve": u"Morph 曲线：",
    "morph_placeholder": u"（仅 Morph 模式）",
    "validate": u"校验",
    "build": u"构建",
    "msg_validate": u"校验",
    "msg_validate_ok": u"校验通过。",
    "msg_see_rows": u"请查看高亮的缝行。",
    "msg_build": u"构建",
    "msg_fix_first": u"请先修正校验错误。",
    "msg_build_done": u"已构建绑定：{0}",
    "msg_build_failed": u"构建失败",
    "edges_count": u"{1} 上的 {0} 条边",
    "pick_warn": u"拾取",
}

_TABLES = {"en": _EN, "zh": _ZH}
