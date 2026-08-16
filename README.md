# HDL-X

HDL-X 是离线、源码到源码的 HDL 转换器。当前 MVP 使用真实 GHDL 语法与语义
分析，将一个受控的、可综合 VHDL-2008 子集转换为可读的 Verilog-2001，同时保留
RTL 层次、范围方向、时序语义与常见源码注释。

当前唯一可用路径是 **VHDL → Verilog-2001**。Verilog → VHDL、SystemVerilog
输入/输出以及完整 VHDL 语言支持均未实现。

## 已支持的 MVP 子集

- entity、单一匹配 architecture、`in`/`out`/`inout` port
- `bit`、`std_logic`、显式范围的 `std_logic_vector`、`signed`、`unsigned`
- integer/natural/positive 与 boolean generic，默认值及 Verilog parameter override
- `to`/`downto`、整数与 generic 驱动的符号范围
- `bit`/boolean/integer 与可证明安全的 vector 基本逻辑、算术、比较和
  条件并发赋值；表达式优先级保持
- 并发简单 signal assignment
- 显式 sensitivity list 的组合 process、`if`/`elsif`/`else`、`case`/`others`、
  有意 latch 形态；生成器保留源 sensitivity 事件语义
- 单时钟 `rising_edge`/`falling_edge` process
- 同步/异步、active-high/active-low reset；时序 signal assignment 生成 `<=`
- 文件内、接口可解析的 direct entity/component 层次实例，named map、可证明安全的
  positional map、`open`
- `for-generate`（to/downto）、`if/else-generate`、嵌套 generate、局部 signal 与实例
- VHDL 大小写不敏感名称解析、Verilog 保留字/非法字符确定性重命名
- 常见 module/port/signal/assignment/process/generate 的 leading/trailing comment
- 结构化诊断（尽可能携带文件、行、列）

## 明确不支持或保守拒绝

HDL-X 的原则是“不确定就失败”，不会为扩大覆盖率静默省略会改变硬件的构造。
当前会结构化拒绝的常见项目包括：

- package/package body/configuration 语义，以及缺失或多个 architecture
- 独立 component-interface/configuration binding 语义与未知外部 component；component
  instance 仅在声明接口可与同文件同名 entity 的名称、顺序、方向、类型和默认值逐项
  证明一致时转换
- process 内声明、多个/模糊时钟、不完整 sensitivity、复杂复位分类
- integer/natural/positive port（当前仅 generic 支持 integer-like 类型）
- wait、after/delay、assert/report、file/access/physical/record/aggregate 等未支持语法
- variable assignment、复杂 waveform、selected assignment 和未实现的并发/顺序节点
- case-generate、elsif-generate、动态（非静态）generate 条件
- 用户函数调用与 type conversion；只有已声明向量对象的一维索引可转换
- VHDL concatenation（结果方向/类型尚未在 canonical expression 中显式建模）
- `process(all)`；当前组合 process 需要显式 sensitivity list
- 组合 process 内同一 signal 的过程写入又被该 process 读取；VHDL delta-cycle
  调度不能用单个 Verilog blocking process 等价表达
- IEEE std_logic/std_logic_vector 的完整 9-state 弱值域：当前精确保留可综合
  `0/1` 与常用 `X/Z` 子域；源码中的 `U/W/L/H/-` 明确拒绝。equality 使用 exact
  comparison 并归一为 VHDL boolean；可能产生 meta 结果的 four-state relational
  comparison 当前保守拒绝
- clock/reset control 假定运行时只有稳定 `0/1` 跳变；VHDL `rising_edge`/
  `falling_edge` 与 Verilog edge control 对 X/Z transition 的定义不同，不承诺这些
  transition 的仿真等价
- VHDL `mod`（负数语义不同于 Verilog remainder，frontend 即结构化拒绝）
- 未显式建模结果位宽的向量 multiply/divide/power
- vector/scalar logical 广播，以及不能静态证明等宽的 vector/vector logical
- 不能静态证明 target/value 等宽的 vector assignment，以及在 generic 默认值或
  override 代换后不能证明 formal/actual 等宽的 instance port connection
- 多驱动、continuous/procedural 混合驱动、未分片的 replicated generate driver
- 初始化值、完整 package 常量求值、configuration/binding 和跨文件 library flow
- `natural`/`positive` 以及受限 integer generic 的 subtype range 约束不会编码进
  Verilog-2001 parameter；默认值与表达式会保留，但目标侧外部 override 必须自行遵守
  源 VHDL 的合法取值范围

这不是综合网表转换器，也不会展开 generate 或 flatten 实例层次。

## 安装

要求 Python 3.10+。开发和验证环境使用 Python 3.13.9 与 pyGHDL/libghdl 6.0.0。
从源码安装运行时依赖：

```powershell
python -m pip install .
```

开发环境使用 editable 安装并加入测试、lint 依赖：

```powershell
python -m pip install -e ".[dev]"
```

VHDL frontend 必须安装与 Python ABI/平台匹配的 **官方 pyGHDL 6.0.0 wheel**。
pyGHDL 的可用 wheel 由 [GHDL 6.0.0 release](https://github.com/ghdl/ghdl/releases/tag/v6.0.0)
分发，而非普通 PyPI 包，因此项目没有声明一个会从 PyPI 拉取错误占位包的运行依赖。
例如 CPython 3.13 64-bit Windows 使用 release asset
`pyghdl-6.0.0-cp313-cp313-win_amd64.whl`：

```powershell
python -m pip install .\pyghdl-6.0.0-cp313-cp313-win_amd64.whl
python -m hdl_x.cli.main doctor
```

项目安装与 pyGHDL wheel 安装的先后顺序不限，但两者缺一不可；`doctor` 会把缺失的
pyGHDL/libghdl 报为 required failure。请评估 pyGHDL/libghdl 的
GPL-2.0-or-later 许可是否符合你的分发方式。独立 GHDL CLI 不是当前 in-process
frontend 的必需项。

## CLI

```powershell
python -m hdl_x.cli.main convert input.vhd --from vhdl --to verilog -o output.v --strict
```

安装脚本目录在 `PATH` 时也可使用：

```powershell
hdl-x convert input.vhd --from vhdl --to verilog -o output.v --strict
```

常用选项：

- `--strict`：默认模式；任何未支持的语义构造或无法安全关联的注释均失败。
- `--best-effort`：只允许安全的非语义损失；当前可省略无法安全关联的源码注释并
  发出 warning，不会跳过任何 RTL 构造，因此 unsafe 构造与 strict 一样失败。
- `--name-style preserve|snake_case|camelCase|PascalCase`：目标名称风格。
- `--validate`：生成后调用可用的 slang/Yosys；缺失的可选工具只产生 warning。
- `--verbose`：成功时报告生成文件路径。

`--strict` 与 `--best-effort` 互斥；两者都不写时默认 strict。失败发生在写输出前，
不会留下 materially incomplete Verilog。

检查真实环境：

```powershell
python -m hdl_x.cli.main doctor
```

`doctor` 将 in-process pyGHDL/libghdl 标为 required，并单独报告 GHDL CLI、slang、
Yosys 等 optional 工具。optional 工具缺失不会令 doctor 失败。

## 桌面 GUI

项目提供基于 Python 标准库 Tkinter 的原生桌面界面，不增加额外 GUI 运行时依赖。
安装项目与 pyGHDL 后，可运行：

```powershell
python -m hdl_x.gui.main
```

安装脚本目录在 `PATH` 时也可运行：

```powershell
hdl-x-gui
```

Windows 还可直接双击仓库根目录的 `HDL-X-GUI.bat`。界面提供输入/输出文件选择、
strict/best-effort、名称风格、可选目标验证、环境检查、VHDL/Verilog 双栏预览以及
结构化诊断。转换在后台线程执行，只在完整转换成功后写入目标文件。

构建独立 Windows EXE：

```powershell
python -m pip install -e ".[exe]"
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build_exe.ps1
```

可靠的分发形式是 `dist\HDL-X\HDL-X.exe` 加同目录的 `_internal` 运行时文件；整个
`dist\HDL-X` 目录需要一起复制。pyGHDL/libghdl 包含 DLL、标准库和 IEEE 资源，
因此默认不压成运行时临时解包的单文件 EXE。构建脚本还会校正 Conda 环境中可能被
ModelSim 等工具 PATH 覆盖的 Tcl/Tk DLL，并在分发目录写入 `使用说明.txt`。

## Python API

```python
from pathlib import Path

from hdl_x.pipeline import ConversionOptions, convert_file

result = convert_file(
    Path("input.vhd"),
    options=ConversionOptions(strict=True, validate=False),
)
Path("output.v").write_text(result.text, encoding="utf-8")
```

使用默认内置 generator 时，`result.design` 是已经过名称与 driver semantic lowering
的语言中立 canonical IR；传入自定义 generator 时，该 generator 通过自身公共契约负责
lowering，`result.design` 保留 frontend 产出的 canonical design。
`result.diagnostics` 包含非致命的 comment omission 或 validator warning。直接构造
canonical IR 并调用 generator 时，所有对象引用仍须在 lexical scope 中声明；仅
Verilog function 名称和显式外部 module 名称可作为外部符号。

## 测试与质量检查

```powershell
python -m pytest -q
python -m ruff check .
python -m compileall -q src tests
```

真实 integration/golden 测试调用 pyGHDL/libghdl，不是 fixture-specific 字符串 parser。
slang 与 Yosys 是可选外部验证器；不可用时测试与 `doctor` 会明确记录。

## 架构

```text
VHDL source
  → PyGhdlBackend（真实 GHDL parse + semantic，立即隔离到私有 Raw IR）
  → VhdlAdapter（Raw IR → language-neutral canonical RTL IR）
  → identifier / driver semantic lowering
  → Jinja2 Verilog-2001 rendering
  → optional slang / Yosys validation
```

canonical IR 不依赖 pyGHDL、IIR 或 VHDL AST 类型。模板只负责布局；名称、driver、
赋值、复位、generate 安全性等判断在 Python lowering 中完成。所有输入先在隔离 arena
执行完整 libghdl semantic pass；这避免把 pyGHDL DOM 的依赖分析误当成 VHDL 名称、
类型与静态性检查。由于 pyGHDL 6.0.0 与当前 pyVHDLModel 的 generate/association DOM
存在 API 漂移，包含 generate 的输入会再重置 arena，并从未被 semantic 改写的低层
IIR 提取 Raw IR。该实现按版本锁定，并由同进程重复解析回归覆盖。
