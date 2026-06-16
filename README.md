# Zipper System

通用「拉链式缝合 (Zipper)」绑定系统 for Autodesk Maya。

从经典的嘴唇拉链 (lip zip / sticky lips) 泛化为**任意曲线对向中间曲线的缝合**：

- **纯曲线模型**：每条缝 = 轨 A + **中间曲线** + 轨 B（三条 NURBS 曲线）；两侧轨随控制器 `zip`
  逐步贴合到中间曲线，`zip=1` 时精确落在其上。
- **不写死上下**：多缝独立，单缝即普通嘴，多缝即 4/5 瓣怪物拉链嘴；各缝各自的控制器 / 方向 / 羽化。
- **实时动态**：纯 Python om-API 1.0 deformer，每帧重算，缝线跟随中间曲线运动。
- **全版本兼容**：Maya 2022.5.1 – 2025.3（**Python 2.7（mayapy2）/ 3.7→3.11 双兼容**，PySide2→PySide6）。

> 当前为纯曲线版：网格 / Morph / 边等模型相关功能已移除，后续按需再加。

## 文档

完整工程架构、算法原理、节点图设计、兼容矩阵与实施顺序见 **[ARCHITECTURE.md](ARCHITECTURE.md)**（唯一事实来源）。

## 状态

✅ P0–P2 已实现（compat / core+单测 / deformer / build / ui / action）。`core` 层 35 项 pytest 全绿；
与 Maya 交互部分提供 Script Editor 手动验证脚本（见下）。

## 快速开始

### 1. 安装

**方式 A — 图形安装程序（推荐）**

双击 `installer\ZipperSystemInstaller.exe`（Windows 单文件，目标机无需 Python）：
勾选目标 Maya 版本（2022–2025，自动检测）→ `Install`。它会把模块内容复制到
`Documents\maya\modules\ZipperSystem\` 并生成 `ZipperSystem.mod`（支持中/英、卸载、按版本增删）。

**重启 Maya 后，顶部菜单栏自动出现「Zipper System」菜单**，并自动加载 `zipperSystem` 插件——
无需在 Plug-in Manager 手动勾选。菜单项：`Open Zipper System UI` / `Load Deformer Plug-in` /
`Rebuild This Menu` / `About`。（菜单与自动加载由模块 `scripts/userSetup.py` 启动钩子完成。）

> 纯 Python om2 deformer，**全版本同一份内容、无需按版本重编**。

> ⚠️ **更新 / 切换设计后必须卸载旧插件（重要）**：Python 插件**不会热重载**。更新本系统、或切换
> deformer 设计后，必须先 `unloadPlugin zipperSystem`、**重启 Maya**，并**删除场景中遗留的旧
> `ddZipperDeformer` 节点**，再重新构建——否则进程里仍是旧字节码，旧节点行为与新源码不一致，会出现
> 「改了代码却没生效」「旧绑定行为诡异」等假象。命令示例：
>
> ```python
> from maya import cmds
> cmds.delete(cmds.ls(type="ddZipperDeformer") or [])  # 先删旧 deformer 节点
> cmds.unloadPlugin("zipperSystem")                     # 再卸载插件，然后重启 Maya
> ```

构建安装程序自身（开发者）：运行 `tools\build_installer.bat`（内部用 PyInstaller 打包，
产物 `installer\ZipperSystemInstaller.exe`）。命令行静默安装：`ZipperSystemInstaller.exe --headless`。

**方式 B — 手动**

把仓库根目录加入 Maya 的 `PYTHONPATH`（或 `sys.path`），使 `import zipper_system` 可用。

### 2. 打开 UI

```python
from zipper_system.action import ZipperAction
ZipperAction.show_ui()
```

多缝列表 `+ Add Seam`；每行 Rail 选 `Edge`/`Curve` 后点 `<` 拾取当前选择；选 `Dynamic` / `Morph`
机制；`Validate` 预检并高亮非法缝；`Build` 事务化构建（失败自动回滚，无孤立节点）。

**界面语言**：右上角下拉框 `English` / `中文` 实时切换，选择跨会话记住。
**帮助气泡**：每个控件旁有 `?` 按钮，悬停弹出该功能的详细中/英说明，点击可钉住浮窗。

### 3. 脚本化构建（无 UI）

```python
from zipper_system.action import ZipperAction
rig_spec = {
    "name": "monsterMouth",
    "build_mode": "native",                   # 默认；下游无需插件。改 "deformer" 走插件版
    "seams": [{
        "mid":   "mid_CRV",                   # 中间曲线（缝线，各轨贴合到它）
        "rails": ["railA_CRV", "railB_CRV"],  # N 条轨曲线（有序，N≥1，默认 2）
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": "jaw_zip_CTRL",
        "zip_attr": "zip",                    # 可选：控制器上的驱动属性名（默认 zip）
    }],
}
ZipperAction.build(rig_spec)          # 校验→建图，返回 rig root
```

每条缝 = **一条中间曲线 + N 条轨曲线**（`rails` 列表，普通嘴用 2 条，多瓣怪嘴按需增减）。构建后拖动
`jaw_zip_CTRL.zip`（0→1）：每条轨逐步贴合到中间曲线，`zip=1` 时所有轨精确落在中间曲线上（两端先合、中央后合）。

> `zip_attr` 为可选字段：控制器上驱动属性的名字（缺省 / 留空即 `zip`）。给不同系统用不同属性名
> （如 `mouthZip` / `eyeZip`）即可**用同一个控制器**分别驱动多套拉链，互不干扰。

> **构建模式 `build_mode`（可选，默认 `native`）**：
> - `native`：仅用 Maya 原生 DG 节点构建，**分发用 native 构建的绑定时下游无需安装本插件**——卸载/未装
>   插件也能打开并动画。UI 里对应「下游需要安装插件」勾选框**保持不勾**。
> - `deformer`：构建紧凑的 `ddZipperDeformer` 插件版（节点更少、性能更好），但下游**必须加载本插件**，
>   否则 deformer 节点连同绑定会一起消失。UI 里**勾选**该框。
>
> 删除绑定：用 `from zipper_system.action import ZipperAction; ZipperAction.delete_rig(rig_root)`
> 可连同 native 辅助节点 / deformer 节点一并干净删除，无残留。

> 当前为**纯曲线版**：已移除网格 / Morph / 边 等模型相关功能（后续按需再加）。

### 4. 验证

```bash
python -m pytest          # core 纯单测（无需 Maya）
```

Maya 内手动冒烟测试：将 `zipper_system/examples/maya_smoke_test.py` 粘进 Script Editor 运行
（`smoke_dynamic()` / `smoke_morph()` / `smoke_validation()`，脚本会打印预期结果）。

> **注 — §3.3 wipe 方向**：蓝图 §3.3 的公式与「两端→中央」文字描述相互矛盾。按维护者决策，
> 系统**两种方向都暴露**：deformer 增加 `invertWipe` 属性（UI 为「Invert wipe」勾选框），
> 默认取「两端→中央」（修正公式 `clamp((z − d_k)/β)`），勾选后还原蓝图「中央→两端」曲线。

## 目录结构

```
zipper_system/
├─ core/        领域层（RailSource / 采样 / 配对 / 数学）— 零 Maya UI 依赖
├─ build/       应用服务层（事务化构建编排）
├─ deformer/    om2 自定义 deformer（纯 Python，免编译）
├─ action/      框架 Action 包装
├─ ui/          PySide2/6 完整界面
├─ compat/      跨版本兼容垫片
└─ tests/       core 层纯单测
```
