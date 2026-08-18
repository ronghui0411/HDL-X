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
- 显式 signal/variable 初始化值、完整 package 常量求值、configuration/binding 和跨文件
  library flow
- `natural`/`positive` 以及受限 integer generic 的 subtype range 约束不会编码进
  Verilog-2001 parameter；默认值与表达式会保留，但目标侧外部 override 必须自行遵守
  源 VHDL 的合法取值范围

这不是综合网表转换器，也不会展开 generate 或 flatten 实例层次。

## 综合语义与仿真初态

Canonical IR 的 `four_state` 会参与 equality/relational、字面量和运算安全检查，也用于
报告源类型边界；但 Verilog-2001 的 `wire/reg` 声明本身不能编码 VHDL `bit` 与完整
IEEE `std_logic` 9-state 类型域。HDL-X v0.1 的主要承诺是声明子集内的可综合状态转移，
不是从仿真时间 0 开始的完整语言级等价：

- VHDL `bit` signal 未写显式初值时从 `'0'` 开始；无初始化的 Verilog `reg` 从 `X`
  开始。
- VHDL `std_logic` 默认从 `'U'` 开始；Verilog 四态没有独立的 `U` 编码。
- 对无复位时序 process，strict 与 best-effort 都保留转换，但返回
  `HDLX-VHDL-INITIAL-STATE` warning，列出受影响状态；任何模式都不会静默声称仿真
  初态等价。
- 有复位时序逻辑只承诺施加有效复位后的状态转移；复位前的 time-zero 初态和
  clock/reset 上的 X/Z edge 行为不在等价承诺内。
- 源码显式 signal initializer 当前以 `HDLX-VHDL-SIGNAL-INITIALIZER` 拒绝，不会丢弃。

因此用于差分仿真时，测试平台必须先施加受支持的显式复位，或自行排除首次有效赋值
之前的样本。若应用要求 FPGA power-up value、VHDL `'U'` 传播或完整 9-state 行为，v0.1
不是合适的转换边界。

## 安装

要求 Python 3.10+。开发和验证环境使用 Python 3.13.9 与 pyGHDL/libghdl 6.0.0。
VHDL frontend 必须安装与 Python ABI/平台匹配的 **官方 pyGHDL 6.0.0 wheel**。
pyGHDL 的可用 wheel 由 [GHDL 6.0.0 release](https://github.com/ghdl/ghdl/releases/tag/v6.0.0)
分发，而非普通 PyPI 包。项目将 `pyGHDL==6.0.0` 声明为核心运行依赖，并要求 backend
与 `doctor` 使用同一条精确版本规则；请先安装匹配 wheel，再安装 HDL-X。
例如 CPython 3.13 64-bit Windows 使用 release asset
`pyghdl-6.0.0-cp313-cp313-win_amd64.whl`：

```powershell
python -m pip install .\pyghdl-6.0.0-cp313-cp313-win_amd64.whl
python -m pip install .
python -m hdl_x.cli.main doctor
```

开发环境在安装 wheel 后使用 editable 安装并加入测试、lint 依赖：

```powershell
python -m pip install -e ".[dev]"
```

缺少 pyGHDL、动态库加载失败或版本不是精确的 6.0.0 时，安装解析、`doctor` 和真实
GHDL 集成测试都会明确失败。请评估 pyGHDL/libghdl 的
GPL-2.0-or-later 许可是否符合你的分发方式。独立 GHDL CLI 不是当前 in-process
frontend 的必需项。

### 许可证与分发状态

HDL-X 自有源码由 `rh` 以 MIT License 发布，版权年份为 2026；完整文本见
[`LICENSE`](LICENSE)。第三方依赖版本、许可证、上游源码和分发边界见
[`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES) 与 [`SBOM.cdx.json`](SBOM.cdx.json)。
这些材料是项目所有者确认后的技术发布记录，不构成法律意见。

v0.1.1 只发布源码和纯 Python wheel，不发布 PyInstaller EXE。两者的依赖边界如下：

- `hdl_x-0.1.1-py3-none-any.whl` **不包含** pyGHDL/libghdl；它只在 metadata 中声明
  `Requires-Dist: pyGHDL==6.0.0`。用户必须先从官方 GHDL release 安装 ABI/平台匹配的
  wheel。由于该 wheel 不在普通 PyPI，完全离线安装还需要单独准备官方 asset。
- `packaging/windows/hdl_x_gui.spec` 会收集 pyGHDL metadata、DLL、标准/IEEE 库，因此
  EXE 是与纯 wheel 不同的二进制分发边界。现有 `dist\HDL-X` 不属于 v0.1.1 Release，
  不上传其目录或 ZIP；未来发布前须单独复核第三方材料、对应源码和代码签名策略。

三种分发边界和 v0.1.1 的所有者决定详见
[`LICENSE_DISTRIBUTION_OPTIONS.md`](LICENSE_DISTRIBUTION_OPTIONS.md)。概要如下：

1. 源码发布：准备项目 LICENSE、NOTICE/第三方清单、完整源码与构建/测试材料；不包含
   pyGHDL 二进制。
2. 纯 Python wheel：在源码材料基础上补 wheel license metadata、依赖/校验清单和官方
   pyGHDL 独立安装/源码获取说明；HDL-X wheel 本身不捆绑 pyGHDL。
3. PyInstaller EXE：再补全部内置组件许可证、NOTICE/SBOM、精确构建源码与经所有者确认
   所需的对应源码获取材料；这是与纯 wheel 不同且更复杂的分发边界。

v0.1.1 采用前两种方式并暂缓第三种。GitHub Release 同时附带 CycloneDX SBOM、
`THIRD_PARTY_NOTICES` 和 SHA-256 清单；不要求 wheel/源码签名。

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

仅用于本地开发验证的 Windows EXE 构建方式如下；v0.1.1 正式 Release 不提供 EXE：

```powershell
python -m pip install -e ".[exe]"
powershell -ExecutionPolicy Bypass -File .\packaging\windows\build_exe.ps1
```

若未来批准分发，可靠形式是 `dist\HDL-X\HDL-X.exe` 加同目录的 `_internal` 运行时文件；整个
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

只运行不依赖真实 GHDL runtime 的单元测试：

```powershell
python -m pytest tests/unit -q -ra
```

报告末尾应明确出现 `GHDL integration: NOT SELECTED (0 tests)`。发布前必须运行：

```powershell
python -m pytest -q -ra --require-ghdl-integration
python -m ruff check .
python -m compileall -q src tests
```

`--require-ghdl-integration` 保证至少选择了一项真实 GHDL 测试；被选择的测试在
pyGHDL 缺失、版本错误或无法加载时会在 collection 阶段失败，不允许用 skip 伪装为
完整通过。报告末尾同时给出 selected/executed/passed/failed/skipped 数量。真实
integration/golden 测试调用 pyGHDL/libghdl，不是 fixture-specific 字符串 parser。
slang 与 Yosys 是可选外部验证器；不可用时测试与 `doctor` 会明确记录。

行为等价测试使用独立的 GHDL CLI 与 Icarus (`iverilog` + `vvp`) 分别运行 VHDL 和
生成的 Verilog，再逐项比较 `HDLX-TRACE`。当前包含 32 组确定性伪随机组合向量，以及
clock/reset/enable 时序轨迹：

```powershell
python -m pytest tests/equivalence -q -ra
python -m pytest tests/equivalence -q -ra --require-semantic-equivalence
```

第一条命令在工具缺失时明确列出 skip 原因，terminal summary 会显示执行数、skip 数和
缺少的程序；第二条是具备完整工具链的 CI/release gate，缺少工具或没有选择等价测试时
直接失败。`Verilator`、`Yosys` 与 `sby` 也会被能力探测记录，但 v0.1 的已实现差分后端
是 GHDL+Icarus。本机若缺少 GHDL CLI/Icarus，这些行为测试必须报告 skipped，不能写成
“已完成等价验证”。

Windows 本地可从 [GHDL 6.0.0 官方 release](https://github.com/ghdl/ghdl/releases/tag/v6.0.0)
取得 standalone mcode/UCRT64 包；Icarus 官方文档推荐 Windows 使用 MSYS2，可在 UCRT64
shell 安装 `mingw-w64-ucrt-x86_64-iverilog`（同时提供 `iverilog.exe` 与 `vvp.exe`）。
若还需要 Yosys/SymbiYosys，YosysHQ 的
[OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) 提供 Windows x64 归档，
激活其 `environment.ps1` 后再检查 `yosys` 与 `sby`。这些安装必须由使用者主动完成，
HDL-X 测试不会自动下载工具。

CI 建议使用 Ubuntu 24.04：以官方 `ghdl/setup-ghdl@v1` 固定 GHDL `6.0.0`/mcode，
安装发行版的 Icarus 包后运行强制等价命令。若增加形式 smoke，可另用
`YosysHQ/setup-oss-cad-suite@v4` 的固定版本提供 Yosys/SymbiYosys；该 job 必须单独报告，
不能替代 GHDL+Icarus 差分 gate。实际 CI 应固定 action commit 或经审核的 release，避免
浮动 nightly 改变门禁结果。

仓库的 `.github/workflows/release-gates.yml` 已将 checkout、Python setup 和 GHDL setup
固定到审核过的完整 commit SHA。semantic-equivalence job 还会校验 Linux CPython 3.13
官方 pyGHDL wheel 的 SHA-256，并对终端汇总强制要求 `passed=2, failed=0, skipped=0`。
完全隔离 wheel smoke 可在 CI 或本地运行：

```powershell
python scripts/release_wheel_smoke.py --workspace <new-empty-directory>
```

脚本创建 `system_site_packages=False` 的新 venv，以完整 wheelhouse 和 `--no-index`
安装，运行 CLI、doctor、真实转换和 golden 字节比较，并输出 HDL-X wheel、pyGHDL wheel、
生成文件与 golden 的 SHA-256。工作目录已存在时脚本会拒绝覆盖。

`slang`/Verilator 对生成 Verilog 的解析、Yosys synthesis smoke 和 Vivado `xvlog`
只能证明目标源码可被相应工具接受；它们不能单独证明与 VHDL 行为等价。Yosys miter 或
SymbiYosys 等价检查只有在源/目标双方都具备可信语义模型时才可计为形式等价结果，当前
环境和 v0.1 默认发行门禁不作此声明。

## 架构

```text
VHDL source
  → PyGhdlBackend（真实 GHDL parse + semantic，立即隔离到私有 Raw IR）
  → VhdlAdapter（Raw IR → language-neutral canonical RTL IR）
  → pipeline-owned VerilogLowering（identifier / driver / storage 决策）
  → VerilogRenderIR（已完成目标 lowering）
  → VerilogRenderer（仅执行 Jinja2 Verilog-2001 rendering）
  → optional slang / Yosys validation
```

canonical IR 不依赖 pyGHDL、IIR 或 VHDL AST 类型。模板只负责布局；名称、driver、
赋值、复位、generate 安全性等判断在 Python lowering 中完成。所有输入先在隔离 arena
执行完整 libghdl semantic pass；这避免把 pyGHDL DOM 的依赖分析误当成 VHDL 名称、
类型与静态性检查。由于 pyGHDL 6.0.0 与当前 pyVHDLModel 的 generate/association DOM
存在 API 漂移，包含 generate 的输入会再重置 arena，并从未被 semantic 改写的低层
IIR 提取 Raw IR。该实现按版本锁定，并由同进程重复解析回归覆盖。

### v0.1 lowering 兼容迁移

新主路径由 pipeline 显式调用 `VerilogLowering.lower()`，再把返回的
`VerilogRenderIR` 交给 `VerilogRenderer.render()`；renderer 不再自行运行名称解析或
driver analysis。`VerilogGenerator.generate(Design)` 与 `generate_lowered(Design)` 仍作为
v0.1 兼容 facade，输出与新路径逐字一致。

为避免破坏现有 Python 调用方和保存的 canonical JSON，v0.1 继续保留
`AssignmentKind.BLOCKING/NON_BLOCKING`、`DriverKind.CONTINUOUS/PROCEDURAL`、
`ProceduralAssignment.assignment_kind` 以及 declaration `driver_kind` 字段；相关 JSON
schema 已标记 deprecated，实例 JSON 结构不变。它们不是长期 canonical 设计方向。
v0.2 才会在独立迁移计划、兼容读取器和版本化 schema 就绪后考虑删除；v0.1 不会静默
改变 `ConversionResult.design` 的节点类型。

### Source location 坐标约定

公开 `SourceLocation.line` 与 `column` 均从 1 开始；comment scanner 的 `offset` 保持为
从文件开头计算的 0-based 字符 offset。`SourceSpan.end` 对 GHDL 可安全识别的声明、
assignment、process、entity/architecture 和 generate 使用终止分号后的半开位置；无法
安全证明终点的节点仍令 `end == start`，不会猜测跨越其他语法节点。

兼容性纠错：v0.1 之前的开发版本曾把 pyGHDL 的 0-based 行内 offset 直接暴露为
canonical/diagnostic column，因而部分 GHDL 节点列号少 1。v0.1 起只在 pyGHDL backend
边界执行一次 `+1`，Raw IR、canonical JSON 和结构化诊断统一为 1-based；line、comment
offset 与生成 Verilog 不变。读取旧开发快照 JSON 的工具如比较列号，应允许旧值相差 1。
