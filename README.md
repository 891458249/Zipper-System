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
    "seams": [{
        "rail_a": "railA_CRV",       # 一侧曲线
        "mid":    "mid_CRV",         # 中间曲线（缝线，两轨贴合到它）
        "rail_b": "railB_CRV",       # 另一侧曲线
        "feather": 0.15, "direction": "both", "invert": False,
        "controller": "jaw_zip_CTRL",
    }],
}
ZipperAction.build(rig_spec)          # 校验→建图，返回 rig root
```

每条缝 = **轨 A + 中间曲线 + 轨 B** 三条 NURBS 曲线。构建后拖动 `jaw_zip_CTRL.zip`（0→1）：
轨 A、轨 B 逐步贴合到中间曲线，`zip=1` 时两轨精确落在中间曲线上（两端先合、中央后合）。

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
