# Zipper System

通用「拉链式缝合 (Zipper)」绑定系统 for Autodesk Maya。

从经典的嘴唇拉链 (lip zip / sticky lips) 泛化为**任意两两对应的 Rail 缝合**：

- **双数据源**：每条轨 (Rail) 可来自 NURBS 曲线 **或** Mesh 边循环（极端网格无法取边时改用曲线）。
- **不写死上下唇**：以「缝 (Seam) = 一对 Rail」为模型，单缝即普通嘴，多缝即 4/5 瓣怪物拉链嘴。
- **双闭合机制**：动态中线（实时跟随，sticky-lips 手感）与静态 Morph（高性能）UI 单选切换。
- **全版本兼容**：Maya 2022.5.1 – 2025.3（Python 3.7→3.11，PySide2→PySide6）。

## 文档

完整工程架构、算法原理、节点图设计、兼容矩阵与实施顺序见 **[ARCHITECTURE.md](ARCHITECTURE.md)**（唯一事实来源）。

## 状态

🚧 开发中 — 架构蓝图已定稿，实现按 `ARCHITECTURE.md` §10 顺序推进。

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
