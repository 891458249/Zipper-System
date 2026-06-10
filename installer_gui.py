# -*- coding: utf-8 -*-
"""Zipper System standalone installer (tkinter GUI + headless backend).

Deploys the Zipper System as a Maya *module*: copies the content tree into the
user's Maya modules directory and writes a ``ZipperSystem.mod`` that routes the
selected Maya versions to it. Because the plugin is pure-Python om2 (no compiled
.mll), the SAME ``scripts/`` + ``plug-ins/`` + ``icons/`` content serves every
supported Maya version (2022.5 - 2025.3) -- nothing to recompile per version.

Run modes:
    python installer_gui.py            # GUI
    python installer_gui.py --headless # install for every detected Maya version
    python installer_gui.py --lang zh  # GUI in Chinese

Packaged into a single .exe via ``tools/build_installer.bat`` (PyInstaller); the
.exe needs no Python on the target machine.
"""

import io
import os
import platform
import shutil
import stat
import sys
import threading
import time


# --------------------------------------------------------------------------- #
# Resource resolution (PyInstaller _MEIPASS vs source run)
# --------------------------------------------------------------------------- #
def _repo_root():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(os.path.realpath(__file__))


_REPO_ROOT = _repo_root()
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


# --------------------------------------------------------------------------- #
# Branding / constants
# --------------------------------------------------------------------------- #
_MODULE_NAME = "ZipperSystem"
_MODULE_VERSION = "0.1.0"
_SUPPORTED_VERSIONS = ["2022", "2023", "2024", "2025"]
_MODULES_SRC = os.path.join(_REPO_ROOT, "modules")

_PLATFORMS = {
    "Windows": "win64",
    "Darwin": "mac",
    "Linux": "linux",
}


def _current_platform():
    return _PLATFORMS.get(platform.system(), "win64")


def _icon_path():
    """Absolute path to the window/exe icon, or None if not found."""
    candidates = [
        os.path.join(_REPO_ROOT, "modules", _MODULE_NAME, "icons",
                     _MODULE_NAME + ".png"),
        os.path.join(_REPO_ROOT, "icons", _MODULE_NAME + ".png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _package_src():
    """Locate the live ``zipper_system`` package (frozen or source run)."""
    candidates = [
        os.path.join(_REPO_ROOT, "zipper_system"),
        os.path.join(_MODULES_SRC, _MODULE_NAME, "scripts", "zipper_system"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


# --------------------------------------------------------------------------- #
# Maya discovery
# --------------------------------------------------------------------------- #
def _default_modules_dir():
    """Default Maya modules directory for the current user."""
    home = os.path.expanduser("~")
    sys_name = platform.system()
    if sys_name == "Windows":
        docs = os.path.join(home, "Documents")
        if os.path.isdir(os.path.join(home, "maya")):
            return os.path.join(home, "maya", "modules")
        return os.path.join(docs, "maya", "modules")
    elif sys_name == "Darwin":
        return os.path.join(home, "Library", "Preferences", "Autodesk",
                            "maya", "modules")
    else:
        return os.path.join(home, "maya", "modules")


def detect_installed_maya():
    """Return {version: install_path} for Maya versions on this machine.

    Filesystem probe of Autodesk's default install location, then a Windows
    registry fallback for relocated installs. Restricted to the versions this
    plugin supports.
    """
    found = {}
    pf = os.environ.get("ProgramFiles", "C:\\Program Files")
    autodesk_root = os.path.join(pf, "Autodesk")
    if os.path.isdir(autodesk_root):
        try:
            entries = os.listdir(autodesk_root)
        except OSError:
            entries = []
        for entry in entries:
            if not entry.startswith("Maya"):
                continue
            ver = entry[len("Maya"):]
            if not (ver.isdigit() and len(ver) == 4):
                continue
            if ver not in _SUPPORTED_VERSIONS:
                continue
            install_path = os.path.join(autodesk_root, entry)
            if os.path.exists(os.path.join(install_path, "bin", "maya.exe")) \
                    or os.path.isdir(os.path.join(install_path, "bin")):
                found[ver] = install_path

    try:
        import winreg
    except ImportError:
        return found
    for ver in _SUPPORTED_VERSIONS:
        if ver in found:
            continue
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            key_path = ("SOFTWARE\\Autodesk\\Maya\\{}\\Setup\\InstallPath"
                        .format(ver))
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    install_path, _ = winreg.QueryValueEx(
                        key, "MAYA_INSTALL_LOCATION")
            except (OSError, FileNotFoundError):
                continue
            if install_path and os.path.isdir(install_path):
                found[ver] = install_path
                break
    return found


# --------------------------------------------------------------------------- #
# Filesystem helpers
# --------------------------------------------------------------------------- #
def _ensure_dir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def _remove_tree(path):
    if not os.path.isdir(path):
        return

    def _on_rm_error(func, fpath, _exc):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_on_rm_error)


def _copy_tree(src, dst):
    """Replace dst with a copy of src, retrying removal (Windows lock lag)."""
    for attempt in range(3):
        try:
            _remove_tree(dst)
            break
        except PermissionError:
            if attempt < 2:
                time.sleep(1)
            else:
                raise
    shutil.copytree(src, dst)


_PKG_IGNORE = shutil.ignore_patterns(
    "tests", "examples", "__pycache__", "*.pyc", "*.pyo")


def _copy_package(src, dst):
    """Copy the zipper_system package, dropping tests/examples/caches."""
    _remove_tree(dst)
    shutil.copytree(src, dst, ignore=_PKG_IGNORE)


# --------------------------------------------------------------------------- #
# .mod generation + parsing
# --------------------------------------------------------------------------- #
def _build_mod_content(content_path, versions):
    """Return ZipperSystem.mod text routing *versions* to *content_path*."""
    plat = _current_platform()
    recursive_icons = (plat != "linux")
    lines = []
    for ver in versions:
        lines.append(
            "+ MAYAVERSION:{ver} PLATFORM:{plat} {name} {version} {path}"
            .format(ver=ver, plat=plat, name=_MODULE_NAME,
                    version=_MODULE_VERSION, path=content_path))
        lines.append("scripts: scripts")
        lines.append("plug-ins: plug-ins")
        lines.append("[r] icons: icons" if recursive_icons else "icons: icons")
        lines.append("")
    return "\n".join(lines) + "\n"


def installed_versions(mod_dir=None):
    """Parse the existing .mod (if any) and return the set of routed versions."""
    if mod_dir is None:
        mod_dir = os.path.dirname(
            os.path.join(_default_modules_dir(), _MODULE_NAME))
    mod_path = os.path.join(mod_dir, _MODULE_NAME + ".mod")
    found = set()
    if not os.path.isfile(mod_path):
        return found
    try:
        with open(mod_path, "r") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("+ ") and "MAYAVERSION:" in line:
                    seg = line.split("MAYAVERSION:", 1)[1].split()[0]
                    if seg:
                        found.add(seg)
    except OSError:
        pass
    return found


# --------------------------------------------------------------------------- #
# Install / uninstall backend
# --------------------------------------------------------------------------- #
def _resolve_paths(install_dir, mod_dir):
    modules_base = os.path.normpath(_default_modules_dir())
    if install_dir is None or not str(install_dir).strip():
        install_dir = os.path.join(modules_base, _MODULE_NAME)
    install_dir = os.path.normpath(install_dir)
    if mod_dir is None:
        mod_dir = os.path.dirname(install_dir)
    return install_dir, os.path.normpath(mod_dir)


def install(install_dir=None, versions=None, verbose=True, mod_dir=None):
    """Install the Zipper System module. Returns True on success.

    *versions* selected Maya versions; None => every supported version. New
    versions are merged with any already routed in an existing .mod (no clobber).
    """
    log = print if verbose else (lambda *a, **k: None)
    install_dir, mod_dir = _resolve_paths(install_dir, mod_dir)

    skeleton = os.path.join(_MODULES_SRC, _MODULE_NAME)
    pkg_src = _package_src()
    if not os.path.isdir(skeleton):
        log("[ERROR] module skeleton not found: {}".format(skeleton))
        return False
    if pkg_src is None:
        log("[ERROR] zipper_system package source not found")
        return False

    if versions is None:
        versions = list(_SUPPORTED_VERSIONS)
    existing = installed_versions(mod_dir=mod_dir)
    effective = sorted(set(versions) | existing)

    log("=" * 60)
    log("  Zipper System Installer  v{}".format(_MODULE_VERSION))
    log("=" * 60)
    log("  Install to   : {}".format(install_dir))
    log("  .mod file in : {}".format(mod_dir))
    log("  Requested    : {}".format(", ".join(versions)))
    log("  Routed (.mod): {}".format(", ".join(effective)))
    log("")

    try:
        log("[1/3] Copying module content ...")
        _ensure_dir(os.path.dirname(install_dir))
        _copy_tree(skeleton, install_dir)              # plug-ins + icons
        _copy_package(pkg_src,
                      os.path.join(install_dir, "scripts", "zipper_system"))
        log("      -> {}".format(install_dir))

        log("[2/3] Writing .mod file ...")
        _ensure_dir(mod_dir)
        mod_path = os.path.join(mod_dir, _MODULE_NAME + ".mod")
        with open(mod_path, "w") as fh:
            fh.write(_build_mod_content(install_dir, effective))
        log("      -> {}".format(mod_path))

        log("[3/3] Installation complete!")
        log("      Restart Maya, then enable 'zipperSystem' in the Plug-in")
        log("      Manager (or run: cmds.loadPlugin('zipperSystem')).")
        log("      Open the UI:  from zipper_system.action import ZipperAction")
        log("                    ZipperAction.show_ui()")
        log("")
        return True
    except Exception as exc:                            # noqa: BLE001
        log("[ERROR] install failed: {}".format(exc))
        return False


def uninstall(install_dir=None, versions=None, verbose=True, mod_dir=None):
    """Remove the module. *versions* removes only those routes; None => all."""
    log = print if verbose else (lambda *a, **k: None)
    install_dir, mod_dir = _resolve_paths(install_dir, mod_dir)
    mod_path = os.path.join(mod_dir, _MODULE_NAME + ".mod")

    log("=" * 60)
    log("  Zipper System Uninstaller")
    log("=" * 60)

    if versions:
        existing = installed_versions(mod_dir=mod_dir)
        remaining = sorted(existing - set(versions))
        log("  Remove   : {}".format(", ".join(versions)))
        log("  Remaining: {}".format(", ".join(remaining) or "(none)"))
        log("")
        if remaining:
            _ensure_dir(mod_dir)
            with open(mod_path, "w") as fh:
                fh.write(_build_mod_content(install_dir, remaining))
            log("  Rewrote .mod, kept content: {}".format(install_dir))
            return True
        # nothing remains -> full removal below

    if os.path.isfile(mod_path):
        os.remove(mod_path)
        log("  Removed .mod : {}".format(mod_path))
    else:
        log("  No .mod at   : {}".format(mod_path))
    if os.path.isdir(install_dir):
        _remove_tree(install_dir)
        log("  Removed dir  : {}".format(install_dir))
    else:
        log("  No content at: {}".format(install_dir))
    log("")
    return True


# --------------------------------------------------------------------------- #
# i18n
# --------------------------------------------------------------------------- #
_STRINGS = {
    "en": {
        "title": "Zipper System Installer",
        "intro": "Install the Zipper System Maya module for the selected "
                 "Maya versions.",
        "versions": "Maya versions",
        "detected": "detected",
        "not_detected": "not detected",
        "routed": "installed",
        "action": "Action",
        "install": "Install",
        "uninstall": "Uninstall",
        "path": "Install path (blank = default):",
        "log": "Log",
        "run": "Run",
        "close": "Close",
        "pick_none": "Select at least one Maya version.",
        "done_ok": "[DONE] {0} succeeded.",
        "done_fail": "[DONE] {0} failed -- see log.",
        "lang": "Language",
    },
    "zh": {
        "title": "Zipper System 安装程序",
        "intro": "为所选 Maya 版本安装 Zipper System 模块。",
        "versions": "Maya 版本",
        "detected": "已检测",
        "not_detected": "未检测到",
        "routed": "已安装",
        "action": "操作",
        "install": "安装",
        "uninstall": "卸载",
        "path": "安装路径（留空 = 默认）：",
        "log": "日志",
        "run": "执行",
        "close": "关闭",
        "pick_none": "请至少选择一个 Maya 版本。",
        "done_ok": "[完成] {0} 成功。",
        "done_fail": "[完成] {0} 失败 —— 见日志。",
        "lang": "语言",
    },
}


def _tr(lang, key):
    return _STRINGS.get(lang, _STRINGS["en"]).get(key, key)


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class _StdoutRedirector(io.IOBase):
    """File-like that forwards writes to a tkinter Text widget."""

    def __init__(self, text_widget):
        self._w = text_widget

    def writable(self):
        return True

    def write(self, msg):
        try:
            self._w.configure(state="normal")
            self._w.insert("end", msg)
            self._w.see("end")
            self._w.configure(state="disabled")
            self._w.update_idletasks()
        except Exception:
            pass
        return len(msg) if msg else 0

    def flush(self):
        return None


class InstallerWindow(object):

    def __init__(self, language="en"):
        import tkinter as tk
        from tkinter import ttk
        self._tk = tk
        self._ttk = ttk
        self._lang = language if language in _STRINGS else "en"

        self._root = tk.Tk()
        self._root.title(_tr(self._lang, "title"))
        self._root.geometry("680x560")
        self._set_icon()

        self._detected = detect_installed_maya()
        self._routed = installed_versions()
        self._version_vars = {}
        self._mode_var = tk.StringVar(value="install")
        self._lang_var = tk.StringVar(value=self._lang)
        self._path_var = tk.StringVar(value="")
        self._build()

    def _set_icon(self):
        path = _icon_path()
        if not path:
            return
        try:
            img = self._tk.PhotoImage(file=path)
            self._root.iconphoto(True, img)
            self._icon_img = img  # keep a ref
        except Exception:
            pass

    def _build(self):
        tk, ttk = self._tk, self._ttk
        pad = {"padx": 10, "pady": 4}

        top = ttk.Frame(self._root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text=_tr(self._lang, "lang") + ":").pack(side="left")
        for code, label in (("en", "English"), ("zh", "中文")):
            ttk.Radiobutton(top, text=label, value=code,
                            variable=self._lang_var,
                            command=self._on_lang).pack(side="left", padx=4)

        ttk.Label(self._root, text=_tr(self._lang, "intro"),
                  wraplength=640).pack(fill="x", **pad)

        # versions
        vbox = ttk.LabelFrame(self._root, text=_tr(self._lang, "versions"))
        vbox.pack(fill="x", **pad)
        for ver in _SUPPORTED_VERSIONS:
            det = ver in self._detected
            routed = ver in self._routed
            var = tk.BooleanVar(value=det)
            self._version_vars[ver] = var
            tags = []
            tags.append(_tr(self._lang, "detected") if det
                        else _tr(self._lang, "not_detected"))
            if routed:
                tags.append(_tr(self._lang, "routed"))
            ttk.Checkbutton(
                vbox, variable=var,
                text="Maya {0}   ({1})".format(ver, ", ".join(tags))
            ).pack(anchor="w", padx=8, pady=1)

        # action
        abox = ttk.LabelFrame(self._root, text=_tr(self._lang, "action"))
        abox.pack(fill="x", **pad)
        ttk.Radiobutton(abox, text=_tr(self._lang, "install"), value="install",
                        variable=self._mode_var).pack(side="left", padx=8)
        ttk.Radiobutton(abox, text=_tr(self._lang, "uninstall"),
                        value="uninstall",
                        variable=self._mode_var).pack(side="left", padx=8)

        # path
        pbox = ttk.Frame(self._root)
        pbox.pack(fill="x", **pad)
        ttk.Label(pbox, text=_tr(self._lang, "path")).pack(anchor="w")
        ttk.Entry(pbox, textvariable=self._path_var).pack(fill="x")

        # log
        lbox = ttk.LabelFrame(self._root, text=_tr(self._lang, "log"))
        lbox.pack(fill="both", expand=True, **pad)
        self._log = tk.Text(lbox, height=12, state="disabled",
                            bg="#11161d", fg="#cfe9e7",
                            insertbackground="#cfe9e7",
                            font=("Consolas", 9))
        scroll = ttk.Scrollbar(lbox, command=self._log.yview)
        self._log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # buttons
        bbox = ttk.Frame(self._root)
        bbox.pack(fill="x", **pad)
        self._run_btn = ttk.Button(bbox, text=_tr(self._lang, "run"),
                                   command=self._on_run)
        self._run_btn.pack(side="right", padx=4)
        ttk.Button(bbox, text=_tr(self._lang, "close"),
                   command=self._root.destroy).pack(side="right", padx=4)

    def _on_lang(self):
        self._lang = self._lang_var.get()
        for child in list(self._root.children.values()):
            child.destroy()
        self._build()

    def _selected_versions(self):
        return [v for v, var in self._version_vars.items() if var.get()]

    def _on_run(self):
        versions = self._selected_versions()
        if not versions:
            self._write(_tr(self._lang, "pick_none") + "\n")
            return
        mode = self._mode_var.get()
        install_dir = self._path_var.get().strip() or None
        self._run_btn.configure(state="disabled")
        t = threading.Thread(
            target=self._run_action, args=(mode, versions, install_dir))
        t.daemon = True
        t.start()

    def _run_action(self, mode, versions, install_dir):
        saved = sys.stdout
        sys.stdout = _StdoutRedirector(self._log)
        try:
            if mode == "install":
                ok = install(install_dir=install_dir, versions=versions,
                             verbose=True)
            else:
                ok = uninstall(install_dir=install_dir, versions=versions,
                               verbose=True)
            key = "done_ok" if ok else "done_fail"
            print(_tr(self._lang, key).format(mode))
        finally:
            sys.stdout = saved
            try:
                self._routed = installed_versions()
                self._run_btn.configure(state="normal")
            except Exception:
                pass

    def _write(self, msg):
        self._log.configure(state="normal")
        self._log.insert("end", msg)
        self._log.see("end")
        self._log.configure(state="disabled")

    def mainloop(self):
        self._root.mainloop()


# --------------------------------------------------------------------------- #
# Headless + entry point
# --------------------------------------------------------------------------- #
def _parse_lang_arg(argv):
    for i, a in enumerate(argv):
        if a == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--lang="):
            return a.split("=", 1)[1]
    return "en"


def _headless_install_all(lang="en"):
    detected = sorted(detect_installed_maya().keys())
    versions = detected or list(_SUPPORTED_VERSIONS)
    print("Headless install for: {}".format(", ".join(versions)))
    return install(versions=versions, verbose=True)


def _selftest():
    """Write a resource-resolution report to a temp file and exit.

    Lets the windowed (no-console) .exe be validated end-to-end: confirms the
    bundled skeleton + package + icon resolve from the PyInstaller _MEIPASS root.
    """
    import tempfile
    skeleton = os.path.join(_MODULES_SRC, _MODULE_NAME)
    checks = {
        "skeleton_ok": os.path.isdir(skeleton),
        "plugin_ok": os.path.isfile(
            os.path.join(skeleton, "plug-ins", "zipperSystem.py")),
        "package_ok": _package_src() is not None,
        "icon_ok": _icon_path() is not None,
        "mod_ok": "MAYAVERSION:2025" in _build_mod_content("X:/x", ["2025"]),
    }
    ok = all(checks.values())
    report = ["frozen={}".format(hasattr(sys, "_MEIPASS")),
              "repo_root={}".format(_REPO_ROOT),
              "package_src={}".format(_package_src())]
    report += ["{}={}".format(k, v) for k, v in sorted(checks.items())]
    out = os.path.join(tempfile.gettempdir(), "zipper_selftest.txt")
    with open(out, "w") as fh:
        fh.write("\n".join(report) + "\nPASS={}\n".format(ok))
    return ok


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    lang = _parse_lang_arg(argv)
    if "--selftest" in argv:
        sys.exit(0 if _selftest() else 1)
    if "--headless" in argv:
        sys.exit(0 if _headless_install_all(lang=lang) else 1)
    if "--uninstall" in argv and "--headless-uninstall" in argv:
        sys.exit(0 if uninstall(verbose=True) else 1)
    InstallerWindow(language=lang).mainloop()


if __name__ == "__main__":
    main()
