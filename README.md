# HDL-X

HDL-X 是离线、源码到源码的 HDL 转换器。已发布稳定基线 `v0.2.0` 提供真实
GHDL 驱动的 VHDL-2008 → Verilog-2001 与真实 Slang 驱动的受控 SystemVerilog →
Verilog-2001。当前开发候选为 **v0.3.0-rc1**（PEP 440 metadata：
`0.3.0rc1`），新增范围明确的 Verilog-2001 → VHDL-2008 综合子集。

三条路径共享语言无关 Canonical RTL IR；目标专属决定分别进入独立的
Verilog/VHDL lowering 与 render IR。v0.3 候选不实现完整 Verilog/SystemVerilog、
SystemVerilog 输出、testbench 语言子集或 Verilog→VHDL 的跨文件工程流。

## VHDL → Verilog-2001 支持范围

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

## SystemVerilog → Verilog-2001 0.2.0 MVP 支持范围

SystemVerilog 输入必须安装精确的 `pyslang==11.0.0` 可选 frontend。已实现范围：

- 单文件 `module`、ANSI ports、大小写敏感标识符
- 可覆盖 `parameter`；受限、无环的 integral `localparam` 在 frontend 私有层安全内联
- `logic`、`reg`、`wire`、单比特与一维 packed vector、signedness 和符号宽度表达式
- 连续 `assign`
- `always_comb`、blocking assignment、`if/else`、精确 `case/default`
- `always_ff`、nonblocking assignment、单一 `posedge`/`negedge` clock
- 常见同步/异步、active-high/active-low reset
- named/positional parameter 与 port connection
- integral literal、索引、切片、拼接、三目和已列入 MVP 的算术/逻辑/比较运算
- 真实 Slang `SyntaxTree` + `Compilation`、Raw → Canonical、pipeline-owned Verilog
  lowering、Jinja2 renderer 的完整磁盘 fixture 路径
- module 边界注释；无法安全关联的内部注释在 strict 中失败，在 best-effort 中明确 warning

signed `parameter int` 只承诺已知 0/1 integral 常量域；`parameter int unsigned` 当前因
Canonical integer signedness/目标 sizing 无法证明而结构化拒绝。two-state `bit` 和数据
对象/port `int` 不能由 Verilog-2001 four-state 变量精确保留，因此结构化拒绝。完整边界和设计理由见
[`V0_2_SYSTEMVERILOG_MVP.md`](V0_2_SYSTEMVERILOG_MVP.md)；正式版本的风险与门禁见
[`V0_2_RELEASE_NOTES.md`](V0_2_RELEASE_NOTES.md)。

## Verilog-2001 → VHDL-2008 0.3.0-rc1 MVP 支持范围

Verilog 输入使用同一精确 `pyslang==11.0.0` 真实前端；parser 对象在私有 Raw 边界前
即被转换为纯 Python 数据。当前候选支持：

- 单文件一个或多个 `module`、ANSI ports、integral `parameter`；
- `wire`、`reg`、`integer`、标量和一维 signed/unsigned packed vector；
- 连续 `assign`，组合 `always @*`/`always @(*)`/简单显式 sensitivity；
- 单时钟 `posedge`/`negedge` 时序 `always`，常见同步/异步高低有效 reset；
- 组合 blocking 与时序 nonblocking assignment、`if/else`、精确 `case/default`；
- 可证明位宽和 signedness 的基本表达式、符号化位宽与参数覆盖；
- 同文件 module 的 named/positional parameter/port connection；
- 带显式 label 的静态 `for-generate`、无 else 的静态 `if-generate`、局部 signal；
- VHDL 保留字和大小写碰撞的确定性改名、1-based source span 与安全关联注释；
- pipeline-owned `VhdlLowering` → `VhdlRenderIR` → 只负责格式化的 Jinja2 renderer。

输出使用 VHDL-2008 `entity`/`architecture`、`std_logic`、`signed`/`unsigned`、
`process(all)`、`rising_edge`/`falling_edge` 与 direct entity instantiation。完整架构和
边界见 [`V0_3_VERILOG_TO_VHDL_MVP.md`](V0_3_VERILOG_TO_VHDL_MVP.md)。

## VHDL 明确不支持或保守拒绝

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

## SystemVerilog 明确不支持或保守拒绝

- `interface`/`modport`、`program`、`package`、`class`、clocking block
- typedef、struct/union/enum、unpacked/dynamic/associative array、queue、string、real
- two-state `bit` 数据对象，以及 `int/integer` 数据 port/signal（parameter 除外）
- task/function、DPI、bind、config、checker、primitive
- `initial`/`final`、assertion/coverage、randomization、mailbox、semaphore
- delay/event/wait/fork-join、force/release、file I/O 和 testbench-only construct
- `always_latch`、普通 `always`、多时钟或复合 event 的 `always_ff`
- wildcard/implicit/interface port connection、任何 include、package/import 和跨文件 compilation unit
- 显式/隐式 generate（包括 generate 局部信号）、宏驱动结构变换和 project flow
- 无读取依赖的 `always_comb`、异步 reset event/条件 polarity 不一致
- unsigned integer parameter、声明初始化、unpacked dimensions、复杂 expression sizing/cast
  和无法证明位宽/符号等价

这些构造通过 Slang syntax/semantic 节点或 adapter 产生 `HDLX-SV-*` 结构化错误；
best-effort 不会跳过任何 RTL/结构节点。

## Verilog → VHDL 明确不支持或保守拒绝

- non-ANSI port、implicit net、跨文件 compilation unit、任何 include、package/import；
- `always_comb`/`always_ff` 等 SystemVerilog 构造，以及 initial/final/delay/wait/testbench；
- sequential blocking、combinational nonblocking、混合 level/edge event、多时钟；
- async reset event 与顶层 reset 条件的信号或 polarity 不一致；
- tri-state/Z driver、多 driver、drive strength 与未建模 resolution；
- mixed signed/unsigned、Slang 检出的隐式截断/不同宽度算术和不安全 resize；
- 无显式 label 的 generate、if-generate else 独立层次、case-generate 与动态 generate；
- function/task、primitive/UDP、casex/casez、复杂宏、数组/存储器和未列出的表达式。

上述 unsafe 构造在 strict 与 best-effort 中都产生精确 `HDLX-V2V-*` 错误。受支持但
语言级仿真不完全等价的边界不会静默：组合 time-zero、X/Z edge、无复位初态、显式 X
和 unsized arithmetic 分别报告 `HDLX-V2V-TIME-ZERO`、`HDLX-V2V-EDGE-META`、
`HDLX-V2V-INITIAL-STATE`、`HDLX-V2V-META-VALUE`、`HDLX-V2V-UNSIZED-SIZING` warning。

这不是综合网表转换器，也不会 flatten 实例层次。

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

SystemVerilog `logic/reg` 与 Verilog `reg` 都是 four-state，未初始化状态均为 `X`；
0.2.0 不把 VHDL 专属初态 warning 套到该路径。two-state `bit/int` 数据对象和显式
initializer 直接拒绝。具有读取依赖的 `always_comb` 降为 `always @(*)` 时返回
`HDLX-SV-ALWAYS-COMB-TIME-ZERO` warning；能够证明没有任何读取依赖、因而目标侧没有触发源的
过程以 `HDLX-SV-ALWAYS-COMB-NO-TRIGGER` 拒绝。clock/reset X/Z transition 返回
`HDLX-SV-EDGE-XZ` warning，只承诺稳定 0/1 edge。已支持的同 signedness 参数表达式保留；
mixed signed/unsigned sizing 以 `HDLX-SV-SIGNED-SIZING` 拒绝，`parameter int unsigned` 以
`HDLX-SV-PARAMETER-SIGNEDNESS` 拒绝。任何 include（包括只定义宏的 `.svh`）、package/import
和跨 compilation-unit flow 都以 `HDLX-SV-COMPILATION-UNIT` 或对应 package 诊断拒绝；
显式或隐式 generate 以 `HDLX-SV-GENERATE` 拒绝。异步 reset 条件与 event polarity 不一致时
以 `HDLX-SV-ASYNC-RESET-EVENT` 拒绝；疑似但未命名为 rst/reset 的复位控制返回
`HDLX-SV-RESET-UNCLASSIFIED` warning 并保留普通 clocked if/else。上述 unsafe 情形在
best-effort 中同样失败。详细边界见 v0.2 发布说明。

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

启用 Slang 驱动的 SystemVerilog 与 Verilog frontend 时，安装精确固定的可选 extras：

```powershell
python -m pip install -e ".[dev,systemverilog,verilog]"
python -m hdl_x.cli.main doctor
```

HDL-X wheel 不捆绑 `pyslang`；metadata 在 `systemverilog` 与 `verilog` extras 中分别
声明同一个 `pyslang==11.0.0`。未安装相应 extra 时，稳定 VHDL 路径仍可用，而请求的
Slang frontend 会以结构化 `HDLX-SV-*` 或 `HDLX-V2V-*` unavailable 诊断失败。

缺少 pyGHDL、动态库加载失败或版本不是精确的 6.0.0 时，安装解析、`doctor` 和真实
GHDL 集成测试都会明确失败。请评估 pyGHDL/libghdl 的
GPL-2.0-or-later 许可是否符合你的分发方式。独立 GHDL CLI 不是当前 in-process
frontend 的必需项。

### 许可证与分发状态

HDL-X 自有源码由 `rh` 以 MIT License 发布，版权年份为 2026；完整文本见
[`LICENSE`](LICENSE)。第三方依赖版本、许可证、上游源码和分发边界见
[`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES) 与 [`SBOM.cdx.json`](SBOM.cdx.json)。
这些材料是项目所有者确认后的技术发布记录，不构成法律意见。

已发布的 v0.1.1 与 v0.2.0 均只采用源码和纯 Python wheel 边界。当前
`v0.3.0-rc1` 仍是未打 tag、未创建 GitHub Release 的候选，也不发布 PyInstaller EXE。
依赖边界如下：

- `hdl_x-0.3.0rc1-py3-none-any.whl` **不包含** pyGHDL/libghdl 或 pyslang/Slang；
  metadata 精确声明核心 `pyGHDL==6.0.0`，并在 `systemverilog`、`verilog` extras
  声明 `pyslang==11.0.0`。完全离线安装需单独准备 ABI/平台匹配的官方 wheels。
- `packaging/windows/hdl_x_gui.spec` 会收集 pyGHDL metadata、DLL、标准/IEEE 库，因此
  EXE 是与纯 wheel 不同的二进制分发边界。现有 `dist\HDL-X` 不属于 v0.3 候选制品；
  未来发布前须单独复核第三方材料、对应源码和代码签名策略。

三种分发边界和项目所有者决定详见
[`LICENSE_DISTRIBUTION_OPTIONS.md`](LICENSE_DISTRIBUTION_OPTIONS.md)。概要如下：

1. 源码发布：准备项目 LICENSE、NOTICE/第三方清单、完整源码与构建/测试材料；不包含
   pyGHDL 二进制。
2. 纯 Python wheel：在源码材料基础上补 wheel license metadata、依赖/校验清单和官方
   pyGHDL 独立安装/源码获取说明；HDL-X wheel 本身不捆绑 pyGHDL。
3. PyInstaller EXE：再补全部内置组件许可证、NOTICE/SBOM、精确构建源码与经所有者确认
   所需的对应源码获取材料；这是与纯 wheel 不同且更复杂的分发边界。

v0.3.0-rc1 继续采用前两种方式并暂缓第三种。候选 CycloneDX SBOM、
`THIRD_PARTY_NOTICES` 和 SHA-256 输出随最终 wheelhouse 重建；只有远端门禁通过并获得
单独发布授权后才可创建 tag/Release，不要求 wheel/源码签名。

## CLI

```powershell
python -m hdl_x.cli.main convert input.vhd --from vhdl --to verilog -o output.v --strict
```

安装脚本目录在 `PATH` 时也可使用：

```powershell
hdl-x convert input.vhd --from vhdl --to verilog -o output.v --strict
```

SystemVerilog v0.2 MVP：

```powershell
hdl-x convert input.sv --from systemverilog --to verilog -o output.v --strict
```

Verilog → VHDL v0.3 候选：

```powershell
hdl-x convert input.v --from verilog --to vhdl -o output.vhd --strict --validate
```

常用选项：

- `--strict`：默认模式；任何未支持的语义构造或无法安全关联的注释均失败。
- `--best-effort`：只允许安全的非语义损失；当前可省略无法安全关联的源码注释并
  发出 warning，不会跳过任何 RTL 构造，因此 unsafe 构造与 strict 一样失败。
- `--name-style preserve|snake_case|camelCase|PascalCase`：目标名称风格。
- `--validate`：Verilog target 调用可用 slang/Yosys；VHDL target 使用固定 pyGHDL 6.0.0 分析。
- `--verbose`：成功时报告生成文件路径。

`--strict` 与 `--best-effort` 互斥；两者都不写时默认 strict。失败发生在写输出前，
不会留下 materially incomplete 目标 HDL。

检查真实环境：

```powershell
python -m hdl_x.cli.main doctor
```

`doctor` 将 in-process pyGHDL/libghdl 标为 required，单独报告可选
`pyslang==11.0.0` frontend，以及 GHDL CLI、slang、Yosys 等外部工具。
未安装 pyslang 不影响 VHDL doctor 结果，但不能执行 SystemVerilog 或 Verilog frontend 转换。

## 桌面 GUI

项目提供基于 Python 标准库 Tkinter 的原生桌面界面，不增加额外 GUI 运行时依赖。
当前 GUI 仍只暴露稳定的 VHDL → Verilog 路径；SystemVerilog 与 Verilog → VHDL 通过 CLI 与
Python API 使用，避免在没有对应交互/诊断回归前扩大 GUI 声明。

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

仅用于本地开发验证的 Windows EXE 构建方式如下；当前 v0.3.0-rc1 候选不提供 EXE：

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

SystemVerilog API 只需显式选择源语言：

```python
result = convert_file(
    Path("input.sv"),
    source_language="systemverilog",
    target_language="verilog",
    options=ConversionOptions(strict=True, validate=False),
)
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

真实 SystemVerilog frontend 回归单独强制：

```powershell
python -m pytest tests/integration -m slang_integration -q -ra --require-slang-integration
```

`--require-ghdl-integration` 保证至少选择了一项真实 GHDL 测试；被选择的测试在
pyGHDL 缺失、版本错误或无法加载时会在 collection 阶段失败，不允许用 skip 伪装为
完整通过。报告末尾同时给出 selected/executed/passed/failed/skipped 数量。真实
integration/golden 测试调用 pyGHDL/libghdl，不是 fixture-specific 字符串 parser；
`--require-slang-integration` 对 pyslang 路径执行同样的零伪装门禁。

行为等价测试使用独立的 GHDL CLI 与 Icarus (`iverilog` + `vvp`) 分别运行 VHDL 和
生成的 Verilog，再逐项比较 `HDLX-TRACE`。当前包含 32 组确定性伪随机组合向量，以及
clock/reset/enable 时序轨迹：

```powershell
python -m pytest tests/equivalence/test_differential_simulation.py -q -ra
python -m pytest tests/equivalence/test_differential_simulation.py -q -ra --require-semantic-equivalence
```

SystemVerilog v0.2 共有四项 Verilog-2001 编译检查和四项组合/signed/reset 极性
差分仿真。原始 `.sv` 以 Icarus `-g2012` 运行，生成 `.v` 以 `-g2001` 运行：

```powershell
python -m pytest tests/equivalence -m systemverilog_equivalence -q -ra
python -m pytest tests/equivalence -m systemverilog_equivalence -q -ra --require-slang-integration --require-systemverilog-equivalence
```

Verilog → VHDL 候选包含 7 个真实 trace 场景，覆盖组合 if/case、clock/reset/enable、
signed arithmetic + parameter、named/positional instance、for/if-generate 与 integer
寄存器。原始 Verilog 用 Icarus `-g2001`，生成 VHDL 用 GHDL `--std=08`：

```powershell
python -m pytest tests/equivalence/test_verilog_to_vhdl_differential.py -q -ra
python -m pytest tests/equivalence/test_verilog_to_vhdl_differential.py -q -ra --require-slang-integration --require-verilog-to-vhdl-equivalence
```

上述三组命令中，各自第一条是普通开发入口：工具缺失时明确列出 skip 原因，terminal
summary 会显示执行数、skip 数和缺少的程序；各自第二条是具备完整工具链的 CI/release
gate，缺少工具或没有选择对应等价测试时直接失败。`Verilator`、`Yosys` 与 `sby` 也会被
能力探测记录；当前三条差分路径分别使用 GHDL+Icarus、SystemVerilog/Verilog 的
Icarus `-g2012`/`-g2001` 双路径。本机缺少这些工具时必须报告 skipped，不能写成
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
独立 `systemverilog-mvp` job 固定 `pyslang==11.0.0` Linux wheel URL 与 SHA-256，
安装 Icarus/VVP；它先强制全部真实 Slang frontend integration 为
`96/96 passed, 0 skipped`，再强制四项 Verilog-2001 编译和四项差分场景为
`8/8 passed, 0 skipped`。新增 `verilog-to-vhdl-mvp` job 还固定 GHDL 6.0.0，
并强制新方向 `7/7 passed, 0 skipped`。本地无独立 simulator 时这些等价测试会明确
skip；只有远端 jobs 实际运行成功后才能声称差分门禁通过。

v0.3 候选门禁见 [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)。仓库
`SBOM.cdx.json` 从最终隔离 wheelhouse 重建，包含 `hdl-x==0.3.0rc1`、
`pyGHDL==6.0.0`、`pyslang==11.0.0` 及 active `systemverilog,verilog` extras 的依赖关系；
同时核对 [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES)。

完全隔离 wheel smoke 可在 CI 或本地运行：

```powershell
python scripts/release_wheel_smoke.py --workspace <new-empty-directory>
```

脚本创建 `system_site_packages=False` 的新 venv，以完整 wheelhouse 和 `--no-index`
安装 `hdl-x[systemverilog,verilog]`，运行 CLI、doctor、三条真实转换和 golden 字节
比较，并输出 HDL-X、pyGHDL、pyslang wheel 及三条生成路径的 SHA-256。工作目录已存在时
脚本会拒绝覆盖。

`slang`/Verilator 对生成 Verilog 的解析、Yosys synthesis smoke 和 Vivado `xvlog`
只能证明目标源码可被相应工具接受；它们不能单独证明与 VHDL 行为等价。Yosys miter 或
SymbiYosys 等价检查只有在源/目标双方都具备可信语义模型时才可计为形式等价结果，当前
环境和 v0.3 候选门禁不作此声明。

## 架构

```text
VHDL source → PyGhdlBackend → Raw VHDL IR → VhdlAdapter ┐
SystemVerilog source → PySlangBackend → pure Raw → SystemVerilogAdapter ├─→ Canonical RTL IR
Verilog-2001 source → PySlangVerilogBackend → pure Raw → VerilogAdapter ┘
  ├─→ pipeline-owned VerilogLowering → VerilogRenderIR → Jinja2 Verilog renderer
  └─→ V2V semantic boundary → pipeline-owned VhdlLowering
      → VhdlRenderIR → Jinja2 VHDL-2008 renderer → pyGHDL/GHDL validation
```

canonical IR 不依赖 pyGHDL、pyslang、IIR 或任何 frontend AST 类型。两套模板只负责布局；
名称、wire/reg/integer storage 和目标赋值操作符在 Verilog lowering 中完成；edge/reset 等源语义在
frontend adapter 规范化为语言无关节点。VHDL 输入先在隔离 arena
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
schema 已标记 deprecated，实例 JSON 结构不变。v0.2 SystemVerilog MVP 继续保留这些
字段作为兼容载体，但实际 `=`/`<=` 决策保存在 `VerilogRenderIR`，renderer 不从
Canonical 字段重新推导目标操作符。删除兼容字段只会在未来独立迁移计划、兼容读取器
和版本化 schema 就绪后考虑；v0.2 不改变 `ConversionResult.design` 的公开节点类型。

### Source location 坐标约定

公开 `SourceLocation.line` 与 `column` 均从 1 开始；comment scanner 的 `offset` 保持为
从文件开头计算的 0-based 字符 offset。`SourceSpan.end` 对 GHDL 可安全识别的声明、
assignment、process、entity/architecture 和 generate 使用终止分号后的半开位置；无法
安全证明终点的节点仍令 `end == start`，不会猜测跨越其他语法节点。

兼容性纠错：v0.1 之前的开发版本曾把 pyGHDL 的 0-based 行内 offset 直接暴露为
canonical/diagnostic column，因而部分 GHDL 节点列号少 1。v0.1 起只在 pyGHDL backend
边界执行一次 `+1`，Raw IR、canonical JSON 和结构化诊断统一为 1-based；line、comment
offset 与生成 Verilog 不变。读取旧开发快照 JSON 的工具如比较列号，应允许旧值相差 1。
