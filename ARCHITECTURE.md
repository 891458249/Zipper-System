# Zipper System — 工程架构蓝图 (Architecture Blueprint)

> 通用「拉链式缝合」绑定系统 for Autodesk Maya。
> 从「嘴唇拉链 (lip zip / sticky lips)」泛化为**任意两两对应的 Rail 缝合**,支持曲线/边双数据源、多瓣怪物嘴、动态/静态双闭合机制。
>
> 本文件是**唯一事实来源 (Single Source of Truth)**。任何实现必须以本文件为准。

---

## 0. 需求基线 (Requirements Baseline)

| # | 需求 | 落点 |
|---|------|------|
| R1 | 数据源支持 **NURBS 曲线** 或 **Mesh 边** 二选一(极端网格无法取边时用曲线) | §2 `RailSource` |
| R2 | 完整 UI(多缝列表、每行可切数据源、动态参数) | §6 |
| R3 | **不写死上下唇**,只需两两对应;支持 4/5 瓣等怪物拉链嘴 | §1 `Seam` 模型 |
| R4 | 兼容 **Maya 2022.5.1 – 2025.3**(Py3.7→3.11 / PySide2→PySide6 / Qt5→Qt6) | §7 |

### 锁定决策 (Locked Decisions)
1. **闭合机制**：动态中线 + 静态 Morph **两者都做**，UI 单选切换。
2. **多缝组织**：**N 条独立 Seam**，各自独立 wipe / 控制器属性，互不耦合。
3. **实现底座**：允许 **纯 Python `maya.api` (om2) 自定义 deformer**，免 C++ 编译 → 跨版本零重编。

---

## 1. 领域模型 (Domain Model)

```
Rail (轨)      : 一条有序 3D 点链；来源 = NURBS 曲线 OR Mesh 边循环
Seam (缝)      : 两条 Rail 的配对 (rail_a, rail_b)，沿中线拉合
ZipperRig (拉链): N 条独立 Seam + 控制器，统一/分别驱动闭合
```

- 普通嘴 = 1 缝 `(上唇轨, 下唇轨)`。
- 4 瓣怪嘴 = 用户自定义 N 缝，两两组配，**代码零硬编码朝向/上下**。
- 由此消除原型代码中的 `upper_edges / lower_edges / negative_z` 三个写死字段。

---

## 2. 核心抽象：`RailSource`（满足 R1 + R3）

```python
class RailSource:            # 抽象基类
    def sample(self, n: int) -> "RailData": ...   # n 个有序世界坐标点 + 回绑信息
    def tangent_at(self, i: int): ...             # 中线法线用
    def bind_handle(self): ...                    # 边: vertex_ids；曲线: param/PointOnCurveInfo

class CurveRail(RailSource):  # maya.api MFnNurbsCurve，按弧长参数采样
class EdgeRail(RailSource):   # 边集 → 邻接图排序成有序顶点路径 → 弧长重采样
```

**统一契约**：无论曲线还是边，上层只拿 `RailData = (points[n], bind[n])`。Seam 的配对/中线/wipe 对数据来源**完全无感**。

**`EdgeRail` 边排序算法**（原型缺失的健壮性）：
1. 选中边是无序集合，需排成单链。
2. 建顶点邻接图：度=1 的顶点为开链端点；全度=2 为闭环。
3. 从一端 DFS/BFS 走出有序顶点序列，复杂度 `O(E)`。
4. 非法情形（分叉 / 多端点 / 跨对象）即时报错并中止，不建任何节点。

---

## 3. 构建管线与数学原理

### 3.1 弧长参数化采样与配对（去掉「上下轨等顶点数」假设）

每条 Rail 按累积弦长归一，第 `k` 个采样参数 `t_k = k/(N-1)`：

```
t^A_i = (Σ_{j≤i} ‖a_j − a_{j-1}‖) / perim(A)
a(t_k) = lerp(a_i, a_{i+1}) | at t_k
```

两轨各取 `t_k` → 配对 `(a_k, b_k)`。**上下轨顶点数可不等**，`pair_count` 退化为采样密度。

### 3.2 闭合机制（双路径）

**动态中线（dynamic，默认）** — 实时算中线，密封线跟随嘴运动：
```
m_k       = ½ (a_k + b_k)
a'_k      = lerp(a_k, m_k, w_k)
b'_k      = lerp(b_k, m_k, w_k)
```
实现 = §A 的 `ddZipperDeformer`。

**静态 Morph（morph）** — 预雕「已闭合」`morph_mesh`，`blendShape(final ← morph)`，wipe 烘焙进权重图。节点 `O(1)/缝`。

### 3.3 拉链推进（corner→center 对称 wipe）

控制器归一量 `z ∈ [0,1]`，`k` 到最近端点的归一距离 `d_k = min(k, N-1-k) / ((N-1)/2)`，羽化带宽 `β`：

```
w_k(z) = clamp( (z − (1 − d_k)) / β , 0, 1 )
```

`z: 0→1` 时各对按 `d_k` 顺序闭合 = 拉链从两端走向中央。`β`、单/双向、左右独立 `zipL/zipR` 均暴露为属性。

---

## 4. 工程分层 (Clean Architecture)

```
zipper_system/
├─ core/                      # 领域层 — 零 Maya UI 依赖，可 CLI/单测独立运行
│  ├─ rail.py                 # RailSource 接口 + RailData
│  ├─ rail_curve.py           # CurveRail (om2)
│  ├─ rail_edge.py            # EdgeRail  (om2, 边排序)
│  ├─ sampling.py             # 弧长重采样、配对  §3.1
│  ├─ seam.py                 # Seam 领域对象
│  └─ math_util.py            # 中线/法线/wipe 公式  §3.2-3.3
├─ build/                     # 应用服务层 — 编排 Maya 节点图
│  ├─ zipper_builder.py       # build(rig_spec) -> rig_root；事务/undo/校验/进度
│  ├─ build_dynamic.py        # 动态档：挂 ddZipperDeformer
│  └─ build_morph.py          # 静态档：blendShape + 权重图
├─ deformer/
│  └─ dd_zipper_deformer.py   # om2 MPxDeformerNode（纯 Python）  §A
├─ action/
│  └─ zipper_action.py        # ActionCore 包装（适配新 rig_spec）
├─ ui/
│  ├─ zipper_widget.py        # 主面板（多缝列表）
│  └─ seam_row.py             # 单缝行控件（曲线/边切换）
├─ compat/
│  └─ qtcompat.py             # PySide2/6、enum、signal、plugin register 垫片  §7
└─ tests/                     # core 层纯单测（无需 Maya GUI）
```

**解耦红线**：
- `core/` 不 import 任何 `cmds` / Qt。
- `build/`、`deformer/` 只用 `cmds` + `maya.api.OpenMaya` 不碰 UI。
- `ui/` 只调 `build` / `core`。
- 核心算法可被 CLI 批处理或单测直接调用。

---

## A. 动态档核心：`ddZipperDeformer`（om2 `MPxDeformerNode`，纯 Python）

**职责**：挂在 `final_mesh` 上，membership = 该缝的缝顶点；实时把 A/B 两侧缝顶点按 wipe 拉向中线。**每缝一个实例**（独立决策）。

**属性契约**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `railA` / `railB` | inputGeometry (curve 或 mesh) | 连入两条驱动轨，deform 时读世界点 |
| `pairCount` | int | 采样密度 N |
| `zip` | float [0,1] | 控制器驱动量 z |
| `feather` | float | 羽化带宽 β |
| `direction` | enum | Both / L→R / R→L |
| `corrA` / `corrB` | int[] | 构建期烘焙「pair k ↔ final_mesh 顶点 id」映射 |
| `envelope` + 逐顶点 `weights` | (内置) | 标准 deformer 衰减，叠乘 w_k |

**`deform()` 核心**（每受影响顶点 → 其 pair k、侧 s）：
```
m_k     = ½ (a_k + b_k)
w_k     = envelope · paint_v · clamp((z − (1 − d_k))/β, 0, 1)
p_out   = lerp(p_in, m_k, w_k)
```
`a_k, b_k` 来自 `railA/railB` 弧长采样（§3.1），逐帧读取 → 中线动态跟随。每帧 `O(V_seam)`，单节点。

**注册/兼容（R4）**：`maya.api.OpenMaya.MFnPlugin.registerNode`，`typeId` 取开发区段 `0x00000–0x7ffff`（或申请正式 id）；纯 Python 插件文件 `loadPlugin` 在 2022.5–2025.3 **API 2.0 稳定、无需重编**。`compat/` 提供统一 register/deregister 入口。

---

## B. 静态档：`build_morph()`

每缝 `blendShape(final ← morph)`，`w_k(z)` 烘焙成沿缝梯度权重图（空间梯度天然表达 wipe 顺序），控制器 → `remapValue` → 全局 target 权重。节点 `O(1)/缝`，GPU 友好，是动态档性能替身。

---

## C. `rig_spec` Schema（取代旧 ACTION_DATA）

```python
rig_spec = {
    "name": str,
    "final_mesh": str,
    "mechanic": "dynamic" | "morph",
    "morph_mesh": str,              # 仅 morph 档校验
    "seams": [                      # ← N 条独立缝 (R3)
        {
            "rail_a": {"type": "edge" | "curve", "handle": <edges | curve>},
            "rail_b": {"type": "edge" | "curve", "handle": <edges | curve>},
            "pair_count": int,
            "feather": float,
            "direction": "both" | "ltr" | "rtl",
            "controller": str,      # 该缝独立控制器/属性
        },
        # ...
    ],
}
```

`rail_a/rail_b.type` 是 R1「曲线或边二选一」的序列化落点；`core.RailSource.from_spec()` 据 `type` 工厂出 `CurveRail` / `EdgeRail`。

---

## 6. UI 设计（R2）

```
┌─ Zipper System ───────────────────────────────┐
│ Rig Name:  [ monsterMouth        ]            │
│ ┌ Seams ──────────────────────────[+ Add][-]┐ │
│ │ ▸ Seam 0  RailA:[Edge ▾][ < ][...sel...]   │ │
│ │           RailB:[Curve▾][ < ][nurbsCrv1]   │ │
│ │ ▸ Seam 1  RailA:[Edge ▾][ < ][...]         │ │
│ │           RailB:[Edge ▾][ < ][...]         │ │
│ └────────────────────────────────────────────┘ │
│ Pair Count:   [  30 ]  (≤ 自动钳制为轨上限)     │
│ Feather β:    [ 0.15]   Direction:[Both ▾]     │
│ Final Mesh:   [ < ][ head_GEO        ]         │
│ Controller:   [ < ][ jaw_zip_CTRL    ]         │
│ Mechanic:     (•) Dynamic midline  ( ) Morph   │
│ Morph Mesh:   [ < ][ ...(仅 Morph 模式可用) ]  │
│                      [ Validate ]  [ Build ]   │
└────────────────────────────────────────────────┘
```

- 每行 Rail 有 `[Edge▾/Curve▾]` 下拉切换来源 → 命中 R1。`<` 按当前模式走 `get_selected_edges` / `get_selected_curve` 校验。
- `[+ Add Seam]` 动态增删 → 命中 R3 任意瓣数。
- `Pair Count` 选定轨后**动态钳制**（修原型 999999 bug）。
- `Validate` 独立预检：不建图，只跑全部校验并高亮错误行。
- 沿用 `model_ctrl` 双向绑定 + `LineEditBoxLayout`；seam 列表用 `QListWidget` + 自定义行控件。

---

## 7. Maya 2022.5.1 – 2025.3 兼容矩阵（R4）

| 维度 | 2022.5 / 2023 / 2024 | 2025.3 | 应对 |
|---|---|---|---|
| Python | 2.7 (mayapy2) **或** 3.7 / 3.9 / 3.10 | 3.11 | **运行期代码 Py2/3 双兼容**：每个模块 `from __future__ import absolute_import, division, print_function`；纯 ASCII 源码；ABC 用 `_add_metaclass` 装饰器（非 `metaclass=`/`__metaclass__`）；节点名判型用 `core._compat.string_types`（Py2 下 cmds 返回 `unicode`）；仅用 3.7 共有语法、不用 3.10+ `match`、注解用字符串。安装程序自身跑在打包 CPython 3.12，不受此约束 |
| Qt 绑定 | PySide2 (Qt 5.15) | PySide6 (Qt 6.5) | 全程经 Qt.py 抽象；禁止直接 `from PySide2` |
| wrapInstance | shiboken2 | shiboken6 | `qtcompat.wrap_instance` try/except 双导入 |
| 枚举作用域 | `Qt.Checked` | `Qt.CheckState.Checked` | 垫片统一常量 |
| 信号 | `stateChanged` | `checkStateChanged`/`toggled` | 统一用 `toggled(bool)` |
| QAction | `QtWidgets.QAction` | `QtGui.QAction` | 垫片别名 |
| `exec_()` / `QRegExp` | 可用 | `exec()` / `QRegularExpression` | 垫片封装 |
| 几何/采样 API | `maya.api.OpenMaya` | 同左（全版本稳定） | 采样/边排序/曲线参数一律 om2 |

`qtcompat.py` 契约：`wrap_instance(ptr, base)` / `CheckState.CHECKED` / `main_maya_window()` / `register_plugin()` / `deregister_plugin()`。

---

## 8. 异常 / 并发 / 校验（事务安全）

- **事务**：`zipper_builder.build()` 顶层 `undoInfo(openChunk=True)` → try → except 记录+反馈+`cmds.undo()` 回滚 → finally `closeChunk`。RAII 式不留孤立节点。
- **预校验**（Build 前必跑）：每缝两轨非空且来源合法、边来自同一对象且可排单链、曲线/`final_mesh`/`controller` `objExists`、`2 ≤ pair_count ≤ 轨上限`、动态模式禁用 morph 字段。
- **进度**：构建循环 `progressWindow`，可 `isCancelled` 中断并回滚。
- **线程**：Maya 节点操作必须主线程；om2 纯数学预采样可子线程，结果回主线程建图，避免大 N UI 假死。

---

## 9. 测试矩阵（core 层无 GUI 单测）

| 用例 | 验证点 |
|---|---|
| 等长 / 不等长两轨 | 弧长配对正确性 |
| 曲线轨 + 边轨混合一缝 | RailSource 抽象一致性 (R1) |
| 单缝 / 4 缝怪物嘴 | 多缝无硬编码 (R3) |
| 闭环 vs 开链边集 | 边排序鲁棒性 |
| z = 0 / 0.5 / 1 | wipe 单调与端点正确 |
| 非法选择（跨对象/分叉） | 校验拦截 + 零节点 |
| PySide2 & PySide6 启动 | UI 兼容 (R4) |

---

## 10. 实施顺序 (Build Order)

| 优先级 | 任务 | 产物 |
|---|---|---|
| P0 | `compat/qtcompat.py` + 插件 register/deregister | 兼容底座 |
| P0 | `core/` RailSource(Curve/Edge) + 边排序 + 弧长配对 | 纯逻辑 + 单测 |
| P1 | `deformer/dd_zipper_deformer.py` + 烘焙 corr 映射 | 动态档核心 |
| P1 | `build_morph.py` blendShape + 权重图 | 静态档 |
| P1 | `zipper_builder.py` 事务/进度/校验，按 mechanic 分发 | 编排层 |
| P2 | `ui/` 多缝面板 + 每行 Edge/Curve 切换 + Mechanic 单选 | 完整 UI |
| P2 | `action/zipper_action.py` 适配新 rig_spec | 框架接入 |
