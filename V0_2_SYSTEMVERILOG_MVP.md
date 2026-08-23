# HDL-X v0.2 SystemVerilog → Verilog-2001 MVP 设计

本文档冻结 v0.2 首个 SystemVerilog 输入切片的兼容边界。实现不得改变 v0.1.1 的
VHDL → Verilog-2001 输出、公开 Canonical IR 节点、Canonical JSON 结构或旧 generator API。

## 基线

- Git 基线：`v0.1.1` / `7bf9785`，开始设计时工作区干净。
- 完整回归：267 passed、2 skipped；真实 GHDL integration 129/129 passed、0 skipped。
- 两项 skip 仅因本机缺少独立 `ghdl`、`iverilog`、`vvp`；强制等价门禁会非零失败。
- Ruff、compileall、pip check 和现有 `tests/golden` diff 均通过。

## 前端选择和依赖边界

采用官方 Slang Python bindings `pyslang==11.0.0`。入口使用 Slang 的 `SyntaxTree` 和
`Compilation` 完成真实预处理、解析、名称解析、类型检查和 elaboration；HDL-X 只在
`parser/slang` 私有层读取 Slang 对象，并立即复制成不含 Slang 类型的私有 Raw IR。

`pyslang` 不加入 v0.1.1 核心依赖。v0.2 将提供精确固定的可选 extra，例如
`hdl-x[systemverilog]`。未安装时：

- VHDL 路径、现有 wheel 安装和发布门禁不受影响；
- 请求 SystemVerilog 转换会以 `FrontendError` / `HDLX-SV-FRONTEND-UNAVAILABLE` 失败；
- SystemVerilog CI/integration 入口必须显式要求真实前端，不能 skip 后报告成功。

在实现前必须实际安装并探测上述精确版本的 API；不依据记忆编造 Slang 接口。

## 支持范围

首个 MVP 只接受单文件、可综合的 SystemVerilog 子集：

- `module` 和 ANSI port declaration；
- 可覆盖 `parameter`；
- 纯 integral、无环 `localparam`，在进入 Canonical IR 前安全内联；
- `logic`、`reg`、`wire`、单比特和一维 packed vector，保留 signedness、four-state
  和范围方向；two-state `bit` 与数据对象 `int` 明确拒绝，`int/integer` 只允许用于
  受限参数；
- 连续 `assign`；
- `always_comb`，过程内 blocking assignment、`if/else` 和精确 `case/default`；
- `always_ff`，单一 `posedge`/`negedge` clock；
- 常见同步/异步、active-high/active-low reset；
- named/positional parameter 和 port connection；
- integral literal、identifier、索引/切片、拼接、三目表达式以及 MVP 运算符；
- symbolic packed width 和由 parameter 构成的范围/默认值/override 表达式。

`localparam` 不作为可覆盖 `Parameter` 伪装进 Canonical IR。Slang `Compilation`
先完成语义检查，adapter 再只对受支持、无环的 integral 表达式按声明顺序展开。例如 `AW = WIDTH - 1`
用于 `[AW:0]` 时保留为 `[WIDTH - 1:0]`。无法安全展开、会引入未支持类型或超出表达式
子集时明确失败。这一 v0.2 MVP 选择保持 JSON 兼容，但不承诺保留 localparam 名称。

## 明确不支持

以下语法即使 Slang 能解析，也必须依据 Slang syntax/semantic node 产生带 1-based span 的
结构化诊断，不能用正则扫描代替：

- `interface`、`modport`、`program`、`package`、`class`、`clocking block`；
- typedef struct/union/enum、unpacked/dynamic/associative array、queue、string、real；
- task/function、DPI、bind、config、checker、primitive；
- `initial`、`final`、assertion/coverage、randomization、mailbox、semaphore、process control；
- delay/event/wait/fork-join、force/release、file I/O 和其他 testbench-only construct；
- `always_latch`、普通 `always`、多事件或语义不明确的 `always_ff`；
- wildcard/implicit port connection、interface port、跨文件 include/package/import；
- generate、宏驱动结构变换和多 compilation-unit flow（首个切片暂不声明支持）。

best-effort 不得跳过上述 RTL/结构节点。安全的注释省略可以 warning；任何可能改变硬件的
省略仍失败。

## Canonical IR 和 lowering 边界

首个切片不新增或删除 Canonical 字段：

- module/port/signal/instance 复用现有节点；
- `always_comb` → `CombinationalProcess(sensitivity=[])`；
- `always_ff` → `SequentialProcess`，edge/reset 进入语言无关语义节点；
- assign/if/case/表达式复用现有 language-neutral 节点；
- localparam 在私有 Raw → Canonical 之前内联，因此不改变 `Module.parameters` 语义。

v0.1 兼容字段 `AssignmentKind`、`DriverKind` 及其 JSON 继续存在，但对新路径只是
deprecated 兼容载体。SystemVerilog adapter 只记录源过程赋值的 scheduling 语义，
不决定目标 wire/reg 或最终文本操作符；pipeline 调用 Verilog lowering，由 process
和 driver evidence 完成 storage 决策，并把 `=`/`<=` 明确记录到独立
`VerilogRenderIR.assignment_operators`。renderer 只消费该 target IR；缺少映射时以
`HDLX-GEN-LOWERING-INCOMPLETE` 失败。

SystemVerilog 标识符大小写敏感。pipeline 会向 identifier lowering 传入大小写策略；默认
仍为现有 VHDL 大小写不敏感策略，以保证旧 API 和 golden 逐字稳定。Canonical JSON 不增加
source-language 字段。

## 公开 API 兼容策略

- `convert_file()` 的参数和 `ConversionResult` 不删除、不改名；`source_language` 新接受
  `systemverilog` 和 `sv`。
- `ConversionResult.design` 仍为现有 `Design` 及公开节点类型。
- `VerilogGenerator.generate(Design)`、`generate_lowered()` 和 VHDL 默认行为不变。
- 旧调用方未选择 SystemVerilog 时不导入 `pyslang`，也不需要安装该 extra。
- CLI 扩展 `--from` 取值，但 VHDL 命令和输出保持不变；首个 MVP 不扩展 Windows GUI。

## 目标文件和测试

已实现：

- `src/hdl_x/parser/slang/{base,raw,pyslang_backend}.py`；
- `src/hdl_x/parser/systemverilog_adapter.py`；
- `src/hdl_x/frontend/systemverilog.py`；
- `tests/fixtures/systemverilog/*.sv`；
- frontend/adapter/pipeline/diagnostic/golden/compile/differential tests；
- 一个强制真实 Slang integration 计数器和 CI job。

保持最小修改：

- `pipeline.py`、CLI、environment/doctor、`pyproject.toml` optional extra；
- Verilog identifier/assignment lowering 的来源策略参数；
- README、PLANS、DEVELOPMENT_LOG 和发布测试说明。

测试必须从磁盘上的真实 `.sv` fixture 调用 `pyslang` 开始，再检查 Raw IR、Canonical IR、
pipeline-owned Verilog lowering、renderer 和新 golden。可用时以 Icarus/Verilator 编译；
组合与 clock/reset/enable 场景做 SystemVerilog 源和生成 Verilog 的差分仿真。缺工具时普通
开发入口明确 skip 原因，强制 CI/release 入口必须失败，不能把 skip 计为 pass。

## 关键语义风险和停止条件

- `logic` 是变量/网类型组合语义，不能按关键词直接映射 wire/reg；必须由 driver evidence
  决定目标声明。
- `always_comb` 有隐式敏感集、单驱动和 time-zero 执行语义；Verilog `always @(*)` 不承诺
  time-zero 调度完全等价，文档和差分采样必须限定边界。
- SystemVerilog 没有语法关键字区分同步 reset 与普通 clocked enable。MVP 只把顶层
  `if/else` 且 reset identifier 命中明确记录的 `rst/reset` 命名约定时分类为
  `ResetSpec(SYNCHRONOUS)`；其他条件保留为普通时序 `IfStatement`。两种渲染保持相同
  clocked RTL 行为，但 Canonical 分类边界必须在文档中可见。
- 当前 Slang backend 为 unsupported syntax/diagnostic 保留精确 1-based span；受支持
  canonical 子节点暂时继承 module span。module 边界注释可保留，无法安全关联的内部
  注释由 strict 拒绝、best-effort warning，不静默丢失。
- `always_ff` 的事件控制、blocking/nonblocking、reset 优先级必须从 Slang 结构读取；任何
  多时钟、复合 event 或不明确 reset 形态保守拒绝。
- SystemVerilog expression sizing、signedness、unsized literal 和 self/context-determined
  规则比现有 IR 更丰富；无法证明目标 Verilog-2001 等价时拒绝，不能靠 best-effort 放行。
- named connection 和模块引用必须使用 Slang 已解析的 symbol；未知 black box 只能在端口
  方向与宽度不需要猜测的有限条件下接受，否则拒绝。
- 若实际 `pyslang==11.0.0` API 无法稳定提供所需 syntax/semantic/source-range 信息，或实现
  必须改变公开 Canonical JSON / v0.1.1 输出，则暂停并请求项目所有者确认。
