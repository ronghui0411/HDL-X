# HDL-X Development Log

本文件记录无人值守 MVP 开发中实际完成的工作与验证结果。只有已执行的命令才记为通过。

## Milestone 0 — Repository and Environment Reconnaissance

- **Status:** completed
- **Implemented:** 完整读取仓库规范与计划；确认仓库为无 Git 的空实现基线；建立标准 `src/` Python 包、Setuptools 构建与 pytest 配置；调查所有要求的本机依赖和工具。
- **Files changed:** `pyproject.toml`, `PLANS.md`, `DEVELOPMENT_LOG.md`
- **Tests executed:** `python -m pytest -q` → 34 passed；`python -m compileall -q src` → passed；`python -m pip install --no-deps --no-build-isolation -e .` → built and installed `hdl-x 0.1.0` successfully。
- **Validation results:** Windows 11 23H2 x64 build 22631.4751；Python 3.13.9 (`E:\\Anaconda\\python.exe`)；Pydantic 2.12.4；Jinja2 3.1.6；Typer 0.20.0；pytest 8.4.2；Setuptools 80.9.0。GHDL、pyGHDL/libghdl、pyslang/slang、Yosys、Icarus Verilog 和 Verilator 均未在初始环境中发现。
- **Important design decisions:** 使用标准 `src/` 布局；`pyproject.toml` 是依赖与构建配置的唯一权威来源；使用本机已有的 Setuptools backend，避免离线环境缺少 Hatchling；外部工具统一通过无 shell 的 subprocess 层调用。
- **Known limitations:** slang 与 Yosys 当前不可用，只影响可选验证。GHDL 是 Milestone 2 的必需 frontend，安装/便携 backend 调查继续进行。
- **Technical debt:** none recorded

## Milestone 1 — Architecture Foundation

- **Status:** completed
- **Implemented:** Pydantic v2 canonical RTL IR（source provenance、comments、types、expressions、statements、combinational/sequential processes、modules、instances、generate）；结构化 diagnostics/errors；Frontend、ParserAdapter、SemanticLowering、Generator、Validator 和 IdentifierResolver 接口；安全 subprocess 层；三类 validator 的 availability/validation 基础。
- **Files changed:** `src/hdl_x/ir/**`, `src/hdl_x/diagnostics/**`, `src/hdl_x/{frontend,parser,generator,transformer,validator,utils}/**`, `tests/unit/**`
- **Tests executed:** `python -m pytest -q` → 34 passed；`python -m compileall -q src` → passed。
- **Validation results:** 包 editable 安装成功；IR JSON round-trip、非法模型、方向范围、symbolic bounds、blocking/non-blocking、clock/reset、instance associations、generate hierarchy、diagnostic spans 和 validator availability 均有单元测试。
- **Important design decisions:** canonical IR 仅表达语言中立的 RTL 语义；assignment operator、clock edge、reset kind/polarity 和 driver kind 显式建模；named/positional association 不允许混用；vector range 同时保留左右边界和方向。
- **Architecture self-review:** 10 项检查均通过：无 GHDL/slang 类型泄漏；范围方向可保留；组合/时序和同步/异步复位可表达；赋值语义显式；实例和 generate 可保留层次；Generator 只依赖 IR；Jinja2 尚不承载语义分析。未发现 unresolved Critical defect。
- **Known limitations:** 尚未接入真实 VHDL frontend，也尚未生成 Verilog；这属于后续里程碑。
- **Technical debt:** `ForStatement` 的 index 必须由合法作用域声明，generator/adapter 需在后续阶段验证，不能隐式制造临时变量。

## Milestone 2 — Minimal VHDL → Verilog Vertical Slice

- **Status:** completed
- **Implemented:** 官方 pyGHDL 6.0.0/libghdl backend；frontend-private Raw VHDL IR；Raw→canonical adapter；entity/architecture/generic/port、`std_logic`/vector、`to`/`downto`、并发赋值、基本算术/逻辑/比较/concat/index 表达式；Jinja2 Verilog-2001 generator；driver/name lowering；Typer `convert`/`doctor`；strict/best-effort 基础；可选目标验证；lightweight comment scanner/source-span association。
- **Files changed:** `src/hdl_x/{frontend,parser/ghdl,parser/vhdl_adapter.py,generator,templates,transformer,validator,cli,pipeline.py,environment.py}/**`, `tests/{unit,integration,fixtures/vhdl,golden}/**`, `pyproject.toml`
- **Tests executed:** `python -m pytest tests/unit/test_vhdl_adapter.py tests/integration/test_ghdl_frontend.py -q` → 6 passed；M2 golden/unsupported/comment tests → 11 passed；frontend/pipeline/CLI tests → 10 passed；`python -m pytest -q` → 94 passed；`python -m compileall -q src` → passed。
- **Validation results:** `python -m hdl_x.cli.main convert tests\\fixtures\\vhdl\\m2_simple_and.vhd --from vhdl --to verilog -o build\\m2_simple_and.v --strict --validate` → conversion succeeded through real libghdl and produced readable `assign y = a & b;`; slang and Yosys each reported unavailable warnings, not false success. Independent `ghdl.exe` is unavailable; parsing uses the installed official libghdl DLL directly.
- **Important design decisions:** pin pyGHDL backend to the actually tested 6.0.0 wheel; use DOM only for GHDL initialization/analysis/navigation and matching libghdl getters for semantic fields where pyVHDLModel 0.39 exposed an observed field mismatch; convert immediately to private dataclasses so DOM/IIR never leaks into canonical IR. `%` is not used for VHDL `mod` until signed operand semantics are explicit. Identifier and driver analysis execute before rendering, not in Jinja2.
- **Known limitations:** current frontend slice rejects processes, conditional assignments, declarations, instances and generate pending later milestones; unsupported delay/process constructs fail structurally even in best-effort mode. No standalone Verilog syntax validator is currently installed.
- **Technical debt:** pyGHDL/libghdl has process-global state and is protected by an in-process lock; future multi-process isolation may improve robustness. pyGHDL licensing implications must be reviewed before redistribution.

## Milestone 3 — Combinational RTL

- **Status:** completed
- **Implemented:** concurrent conditional assignment→ternary；sensitivity-list combinational process；recursive if/elsif/else；basic case/others；procedural signal assignment→blocking；output wire/reg driver inference；vector processes；intentional latch preservation；structured wait/delay/unknown sequential diagnostics。
- **Files changed:** `src/hdl_x/parser/ghdl/{raw.py,pyghdl_backend.py}`, `src/hdl_x/parser/vhdl_adapter.py`, `src/hdl_x/transformer/type_lowering.py`, `tests/{fixtures/vhdl,integration,unit}/**`
- **Tests executed:** GHDL/adapter targeted → 16 passed；`python -m pytest -q` → 106 passed；`python -m compileall -q src` → passed；scoped Ruff → passed。
- **Validation results:** 7 representative fixtures were converted through the CLI: `conditional_assignment`, `if_else_mux`, `nested_if`, `vector_process`, `output_reg`, `case_logic`, `latch`. Outputs contained ternary `assign`, `always @(*)`, blocking `=`, `output reg`, nested if/case, and preserved the intentional incomplete latch branch. No external Verilog validator was available.
- **Important design decisions:** process classification is based on structured GHDL/IIR nodes, never sensitivity-list text replacement；VHDL signal assignment in a combinational process is lowered to canonical blocking semantics；case `others` maps to default；incomplete source assignments remain incomplete instead of inventing defaults；driver analysis is path-sensitive across mutually exclusive if-generate branches and rejects unsafe multiple drivers.
- **Known limitations:** sequential/clocked processes remain for Milestone 4；process-local declarations and unsensitized processes are explicitly unsupported；case choices are limited to safely mapped static expressions.
- **Technical debt:** canonical process IR still lacks local declaration scope; procedural loop indices require explicit module-level integer variables until that IR gap is addressed.

## Milestone 4 — Sequential RTL

- **Status:** completed
- **Implemented:** structured rising/falling-edge classification；single-clock sequential process；sync/async high/low reset；counter and multi-register bodies；recursive NON_BLOCKING lowering；sensitivity-set validation；clock-enable preservation；diagnostics for ambiguous clocks/resets, incomplete async sensitivity and unsupported process declarations.
- **Files changed:** `src/hdl_x/parser/ghdl/{raw.py,pyghdl_backend.py}`, `src/hdl_x/parser/vhdl_adapter.py`, `tests/fixtures/vhdl/m4_*.vhd`, `tests/{integration,unit}/test_*sequential*.py`
- **Tests executed:** M4 integration → 15 passed；M4+adapter+generator → 33 passed；`python -m pytest -q` → 134 passed；scoped Ruff → passed；`python -m compileall -q src` → passed。
- **Validation results:** all eight positive fixtures were converted through the real CLI. Generated headers were verified for posedge/negedge, sync reset excluded from sensitivity, async reset included with the correct edge, active-high/low conditions, and non-blocking assignments. Four misclassification/sensitivity negative cases produced structured diagnostics. No external Verilog validator was available.
- **Important design decisions:** accept only exact structured `rising_edge`/`falling_edge` single-argument calls with a simple clock present in the sensitivity list；classify reset from nested/elsif IIR structure rather than source text；async sensitivity must be exactly clock+reset；unsafe ambiguity fails explicitly.
- **Review finding and fix:** independent review reproduced a sequential process-local constant being silently omitted, producing an undeclared Verilog reference. The common GHDL process entry now rejects any unsupported local declaration before classification with `HDLX-VHDL-PROCESS-DECLARATION`; strict and best-effort regression both verify file/line diagnostics.
- **Known limitations:** single clock only；simple clock name only；reset condition is limited to a simple signal compared with `'0'`/`'1'`；process-local declarations are diagnosed rather than lowered；aggregate reset literals remain outside the expression subset.
- **Technical debt:** richer process-local scopes require a canonical IR extension before support can be added safely.

## Milestone 5 — Generic / Parameter Support

- **Status:** completed
- **Implemented:** integer/natural/positive generics→Verilog integer parameters；literal and expression defaults；multiple generics；symbolic vector bounds preserving `to`/`downto`；parameterized combinational modules and counters；canonical parameter-binding representation. Boolean generic 随后由 M6/M7 真实 generic-map/generate fixtures 覆盖。
- **Files changed:** `tests/fixtures/vhdl/m5_*.vhd`, `tests/golden/m5_*.v`, `tests/integration/test_m5_generics.py` (implementation reused and exercised the Milestone 2/4 frontend, IR and generator layers).
- **Tests executed:** M5 targeted → 11 passed；current full suite → 134 passed.
- **Validation results:** six real VHDL inputs passed through libghdl→Raw IR→canonical IR→Verilog and matched complete golden files. Symbolic `VectorRange.width` remained `None`, bounds were not flattened, ascending and descending ranges remained distinct, and the parameterized counter used non-blocking assignments.
- **Important design decisions:** preserve symbolic expression trees instead of evaluating defaults into widths；generic defaults and module ranges reference the same resolved parameter names；parameter overrides remain explicit bindings for hierarchy lowering.
- **Known limitations:** real generic-map instance overrides are Milestone 6；scalar integer/natural/positive/boolean 以外的 generic 类型不在当前 MVP。
- **Technical debt:** no general VHDL constant evaluator; only expressions representable safely in target Verilog remain symbolic.

## Milestone 6 — Hierarchical Instance Support

- **Status:** completed
- **Implemented:** architecture signal declarations including multi-identifier subtype inheritance；direct entity and component instances；instance labels/referenced units；named and safe known positional generic/port maps；open port bindings；multiple design units per file without flattening；scope-aware target identifier resolution and collision handling.
- **Files changed:** `src/hdl_x/parser/ghdl/{raw.py,__init__.py,pyghdl_backend.py}`, `src/hdl_x/parser/vhdl_adapter.py`, `tests/fixtures/vhdl/m6_*.vhd`, `tests/golden/m6_*.v`, `tests/{unit,integration}/test_*hierarchy*.py`, `tests/integration/test_m6_generator_contract.py`
- **Tests executed:** M6 frontend targeted → 14 passed；canonical generator contract → 12 passed；M2–5 regression → 43 passed；`python -m pytest -q` → 170 passed；full Ruff → passed；`compileall -q src tests` → passed。
- **Validation results:** four real VHDL hierarchy fixtures converted through libghdl and the CLI. Manual review confirmed explicit child/top modules, preserved intermediate signals and instance labels, named generic/port connections, positional connections, and open output. No external Verilog validator was available.
- **Important design decisions:** use low-level libghdl IIR for design-unit, declaration, instance and association structure because actual pyGHDL 6.0.0/pyVHDLModel 0.39 association fields were observed reversed；never parse `=>` text；`open` is a distinct association kind and never passed to `Get_Actual`；positional associations are accepted only when a referenced entity interface is available in the same RawDesign and bounds can be checked。Component declarations are retained with generic/port types, directions and defaults, and a component instance is bound only when that interface can be proven item-for-item equivalent to a same-file entity.
- **Known limitations:** independent/external component-interface semantics remain unsupported；component/entity name, order, direction, type or default mismatches are rejected rather than guessed；positional instances referencing unknown external units are rejected；configuration specifications/bindings are unsupported.
- **Technical debt:** milestone close 时 positional open 仍以空 ordered connection 和稀疏空白渲染；Milestone 8 readability review 已改为显式 `/* open */` 并统一实例缩进，且未改变 port position。

## Milestone 7 — Generate and Comment Preservation

- **Status:** completed
- **Implemented:** for-generate (`to`/`downto`)；if-generate with else；nested generate；generate-local signals and instances；preserved labels/hierarchy；isolated low-level libghdl fallback for DOM-incompatible generate files；real source comment scanning, safe source-span association and recursive attachment to canonical nodes.
- **Files changed:** `src/hdl_x/parser/ghdl/{raw.py,__init__.py,pyghdl_backend.py}`, `src/hdl_x/parser/vhdl_adapter.py`, `src/hdl_x/frontend/{comments.py,vhdl.py}`, `tests/fixtures/vhdl/m7_*.vhd`, `tests/golden/m7_*.v`, `tests/{unit,integration}/test_*generate*.py`, `tests/integration/test_comment_preservation.py`, M2 comment golden/regression.
- **Tests executed:** M7 generate/comment targeted → 25 passed；canonical generator/comment contract → 10 passed；scanner/comment/M2 targeted → 21 passed；`python -m pytest -q` → 185 passed；full Ruff → passed；`python -m compileall -q src tests` → passed。
- **Validation results:** four real generate designs and a real comment-rich design converted through the CLI and matched complete goldens. A same-process normal→generate→normal→generate→normal regression passed, proving fallback lifecycle repeatability. No external Verilog validator was available.
- **Important design decisions:** 所有输入先在独立 arena 执行完整 libghdl semantic pass，不能把高层 DOM 的依赖分析当作名称、类型与静态性检查；normal files 随后使用稳定 DOM 提取路径；包含 generate 或命中已知 generate translation `TypeError` 的输入在第二次 `Design()` reset 后以 `Document(..., dontTranslate=True)` 直接提取未被 semantic 改写的 IIR。semantic pass 临时插入的 work-library design units 在 pass 结束时立即 purge，提取 arena 与 semantic arena 隔离；同进程 normal/generate 交错解析回归覆盖其生命周期。Generate is represented, not unrolled. Comments use a lightweight scanner only for trivia, never grammar parsing.
- **Comment policy:** safe nearest-node association is bounded by source gaps and structural headers；comments are attached once in source order；unassociated comments remain queryable；library/use/architecture header comments are not guessed onto unrelated RTL nodes。Milestone 8 pipeline policy 后续明确为 strict 拒绝静默丢弃未关联注释、best-effort 省略并返回 warning。
- **Known limitations:** elsif-generate and case-generate are explicitly diagnosed；comment mapping is best-effort and does not reproduce whitespace exactly；full end spans are unavailable for many libghdl nodes.
- **Technical debt:** generate fallback depends on a verified pyGHDL 6.0.0 initialization boundary and private design-file access；a future officially stable structured API should replace it when available.

## Milestone 8 — MVP Integration, Regression and Review

- **Status:** completed
- **MVP status:** VHDL → Verilog-2001 MVP 已完成端到端集成、回归、独立语义审计与外部 Verilog 编译复核；Milestone 0–8 均已完成。最终审计重放所有已报告反例后，当前声明子集内没有已知未修 Critical RTL semantic bug。
- **Implemented syntax:** 单一 entity/architecture、ports/signals、scalar/vector/signed/unsigned、integer/boolean generic 与 symbolic ranges；并发及条件赋值；显式 sensitivity 的组合 process、if/case/latch；单时钟 rising/falling-edge 及时序 reset；direct/component instance、named/positional/open、generic override；for/if/else/nested generate 与局部 signals；确定性标识符解析、driver analysis 和安全源码注释关联。完整支持边界以 `README.md` 为准。
- **Integration and review fixes:** 所有输入统一执行独立 libghdl semantic pass；package/package body/configuration design units 和缺失 architecture 不再静默降级；explicit sensitivity 不再改写成 `@(*)`；组合 process 的 signal 写后读/delta-cycle 风险显式拒绝；strict 拒绝未关联注释，best-effort 仅省略该非语义信息并返回 warning；实例缩进和 positional `open` 可读性已统一；component/entity interface 按名称、顺序、方向、类型与默认值逐项证明；integer port 拒绝；signed/unsigned 与 X/Z 派生表达式的 equality/relational 按已证明安全的子域归一；vector logical、算术、assignment 与 instance port 的 symbolic width 无法证明时保守拒绝。
- **Known unsupported syntax:** package/configuration 与跨文件 library flow、独立未知 component interface、process-local declarations/variables、多时钟或复杂 reset、组合 process signal 自依赖、wait/delay/assert/file/advanced types、integer port、process(all)、selected assignment、case/elsif-generate、VHDL concat、用户函数/type conversion、`mod`、不能证明等宽的 vector assignment/instance connection、未建模结果位宽的 vector multiply/divide/power、弱态 `U/W/L/H/-` 和不安全多驱动。unsupported 语义构造在 strict 与 best-effort 均失败。
- **Tests executed:** 最终 `python -m pytest -q -p no:cacheprovider` → 228 passed in 5.19s；重点 semantic/hierarchy/generate/sequential/pipeline 集成命令 → 82 passed；独立审计的 13 个历史 Critical 反例重放 → 13 passed；`python -m ruff check .` → all checks passed；`python -m compileall -q src tests` → passed。
- **CLI and packaging smoke:** `python -m hdl_x.cli.main --help` 与 `convert --help` → passed；真实 `convert ... --strict --validate --verbose` → generated expected Verilog，slang/Yosys 缺失均产生 warning；`python -m pip wheel --no-deps --no-build-isolation .` → built `hdl_x-0.1.0-py3-none-any.whl`，wheel 含 3 个 Jinja2 templates；installed metadata 暴露 `hdl-x = hdl_x.cli.main:app`。当前 shell 的 scripts 目录不在 `PATH`，因此本机实际 smoke 使用 package-entry equivalent，README 已明确 direct `hdl-x` 的 PATH 前提。
- **Validation status:** `python -m hdl_x.cli.main doctor` → exit 0；Python 3.13.9 available；required pyGHDL/libghdl 6.0.0 available，真实 integration 通过 universal semantic pass；standalone GHDL CLI unavailable (optional)；slang CLI unavailable (optional)；Yosys CLI unavailable (optional)。未把 unavailable validator 记为通过。Vivado Simulator 2023.2 `xvlog` 作为独立补充验证：21 个 committed golden Verilog 文件一次性编译 exit 0；另将 21 个代表性 VHDL fixture 逐个通过真实 CLI 重新转换，21/21 转换成功且 21/21 生成输出分别由 `xvlog` 编译成功。最终参数化 counter CLI smoke 也以 strict+validate+verbose 成功生成，并由 `xvlog` 分析通过。
- **Known technical debt:** pyGHDL/libghdl 是 process-global state，当前以锁、arena reset 和私有 design-file access 隔离；generate fallback 依赖已验证的 6.0.0 API 边界；comment end spans 不完整；没有通用 VHDL constant evaluator 或多文件 project/library model。该阶段尚未完成的许可证决定已在后续 v0.1.1 release preparation 中由项目所有者补齐。
- **Known semantic limitations:** 只承诺 README 声明的可综合子集；不提供完整 IEEE std_logic 9-state 等价性，clock/reset 的 X/Z transition 也不承诺与 VHDL edge function 等价；`natural`/`positive`/受限 integer generic 的 subtype range 不会编码进 Verilog parameter，目标侧 override 必须遵守源范围；不展开 generate，不 flatten 层次，不把 synthesis/netlist 作为翻译 IR；无法静态证明 expression/connection width 时宁可拒绝。缺少声明的可选目标 validator 时，由 golden/IR 回归、独立语义反例审计及本机 Vivado `xvlog` 批量编译补充验证。
- **Recommended next phase:** MVP 已冻结。后续在新的用户请求下，优先建立 Windows/Linux/macOS CI、安装 slang/Yosys 的独立 target validation、明确发布许可，并在稳定官方 pyGHDL structured API 可用时替换私有 fallback；不自动启动 Verilog → VHDL、SystemVerilog 或 Phase 2。

## Post-MVP — Tkinter Desktop GUI

- **Status:** completed
- **Implemented:** 新增原生 Tkinter 桌面应用，提供 VHDL/Verilog 文件选择、strict/best-effort、名称风格、可选 validator、环境检查、双栏源码预览、结构化诊断、进度状态和覆盖确认；转换在 daemon worker 中执行，所有 Tk 控件只由主线程更新。业务编排独立在 GUI controller 中，继续复用既有 `convert_file` pipeline，不复制 frontend、lowering 或 generator 逻辑。
- **Files changed:** `src/hdl_x/gui/{__init__.py,controller.py,main.py}`, `tests/unit/test_gui_controller.py`, `tests/integration/test_gui.py`, `HDL-X-GUI.bat`, `pyproject.toml`, `README.md`, `DEVELOPMENT_LOG.md`。
- **Tests executed:** `python -m pytest tests/unit/test_gui_controller.py tests/integration/test_gui.py -q -p no:cacheprovider` → 9 passed；最终 `python -m pytest -q -p no:cacheprovider` → 237 passed in 6.73s；`python -m ruff check .` → all checks passed；`python -m compileall -q src tests` → passed。
- **Validation:** 当前 Python 实测 Tkinter 8.6；程序化创建 `Tk` root 与完整 `HDLXApplication` widget tree 成功；真实 GUI controller 经 pyGHDL/libghdl 转换 `simple_logic.vhd` 并写出预期 Verilog；`pip wheel --no-cache-dir --no-deps --no-build-isolation .` 构建成功，wheel 包含三个 GUI 模块，metadata 同时包含 `hdl-x` console script 与 `hdl-x-gui` GUI script。
- **Important decisions:** Tkinter 属于 Python 标准库，避免为桌面入口增加大型依赖；耗时转换不阻塞事件循环；输入源文件不可被输出覆盖；转换失败不会创建目标文件；CLI 与 Python API 行为保持不变。
- **Known limitations:** GUI 仍遵循单文件 VHDL MVP，不提供多文件 project/library 管理；后台任务当前不能中途取消；拖放和波形/原理图视图不在本次范围。
- **Technical debt:** 如后续需要更复杂的工程管理或跨平台视觉一致性，可在不改变 controller/pipeline 契约的前提下替换 presentation layer。

## Post-MVP — Windows EXE Distribution

- **Status:** completed
- **Implemented:** 使用 PyInstaller 6.22 生成 Windows x64 目录版 GUI 应用，入口为 `dist/HDL-X/HDL-X.exe`；分发目录内置 CPython、Tkinter、pyGHDL/libghdl DLL、VHDL 标准/IEEE 库、Jinja2 模板及使用说明，目标机器不需要另装 Python/GHDL。启动失败会在 EXE 同目录写 `HDL-X-error.log`。
- **Packaging policy:** 使用 one-folder 而非 one-file，确保 libghdl 与标准库拥有稳定资源路径；构建脚本拒绝覆盖已有 dist/work 目录，并优先复制当前 Python 环境匹配的 Tcl/Tk DLL，避免 ModelSim 等 PATH 条目导致 Tcl 脚本/DLL 版本错配。
- **Validation:** 实际启动冻结后的 GUI，使用 `m2_simple_and.vhd` 完成 VHDL → Verilog 转换；生成文件与 golden 逐字一致，界面输出预览和成功诊断正常。分发包包含 4 个 GHDL DLL、75 个 VHDL 库源文件和 2 个已编译库索引。
- **Tests executed:** `python -m pytest -q -p no:cacheprovider --basetemp build/pytest-final-20260817` → 237 passed；`python -m ruff check .` → all checks passed；`python -m compileall -q src tests packaging/windows` → passed。最终目录约 65.19 MiB，ZIP 约 27.95 MiB，并已检查 ZIP 同时包含 EXE、使用说明和 libghdl。
- **Known limitations:** 当前 EXE 未做数字签名；分发时必须保留完整 `HDL-X` 目录。对外再分发前仍需完成项目许可证及 pyGHDL GPL-2.0-or-later 合规决策。

## v0.1 Release Hardening — Integration, Semantics and Verification

- **Status:** implementation completed；distribution approval remains conditional on the project/license decision described below.
- **Test reliability:** `doctor` 与 `PyGhdlBackend` 统一使用 exact `pyGHDL==6.0.0` runtime probe；核心 dependency metadata 也精确声明该版本。真实 frontend tests 使用 `ghdl_integration` marker，缺失/错误/不可加载 runtime 时 collection 直接失败；`--require-ghdl-integration` 防止 release 命令漏选真实测试。unit-only 与 full run 的 terminal summary 都明确显示 integration 是否执行，不再使用 `importorskip`。
- **Semantic boundary:** 新增 `HDLX-VHDL-INITIAL-STATE` warning。无复位 `bit` 状态的 VHDL `'0'` 初态与 Verilog `X`、`std_logic` 的 `'U'` 与 Verilog 四态不可精确编码均不再静默；显式 signal initializer 继续以 `HDLX-VHDL-SIGNAL-INITIALIZER` 拒绝。文档只承诺声明子集内的综合状态转移和施加复位后的行为，不宣称 time-zero/完整 IEEE 9-state 等价。
- **Lowering boundary:** pipeline 现在显式拥有 `VerilogLowering -> VerilogRenderIR -> VerilogRenderer` 主路径；renderer 不运行 identifier/driver lowering。`VerilogGenerator.generate()`/`generate_lowered()` 保留为 v0.1 facade。`AssignmentKind`、`DriverKind` 与现有 JSON 字段保留且 schema 标记 deprecated，v0.2 才可在版本化迁移中考虑删除。6 个 M2 真实设计证明旧 API、新主路径与 committed golden 逐字一致。
- **Source provenance:** pyGHDL 的 0-based 行内 offset 只在 backend 边界转换一次，Raw/canonical/diagnostic column 从 v0.1 起统一 1-based；comment character offset 保持 0-based。基于 IIR 节点类别的窄词法终止扫描补全多行 signal declaration、assignment、normal/fallback process 与 generate 的半开 end span，不启用会破坏 generate arena 生命周期的 libghdl elocation flag。strict 对无法关联注释结构化失败；best-effort warning 现在列出省略注释的位置、文本与 snippet。
- **Equivalence infrastructure:** 新增 GHDL CLI + Icarus (`iverilog`/`vvp`) 五步差分 harness，比较标准化 `HDLX-TRACE`；包含 32 组确定性伪随机组合向量和 clock/reset/enable 时序轨迹。`--require-semantic-equivalence` 在工具缺失或测试未被选择时失败；普通环境允许明确 skip。Verilator/Yosys/SymbiYosys 只做能力探测，syntax/synthesis smoke 不冒充行为等价或形式证明。
- **Final tests executed:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --basetemp build\\pytest-v01-release-final` → **267 passed, 2 skipped in 9.01s**；真实 in-process GHDL integration **129/129 passed, 0 skipped, pyGHDL 6.0.0**；semantic equivalence **0 passed, 2 skipped**，明确原因是缺少 `ghdl`, `iverilog`, `vvp`。`python -m ruff check .` → all checks passed；`python -m compileall -q src tests packaging\\windows` → passed。
- **Packaging/environment validation:** `python -m hdl_x.cli.main doctor` → required Python 3.13.9 与 pyGHDL/libghdl 6.0.0 available；standalone GHDL CLI、slang、Yosys unavailable/optional。`python -m pip check` → no broken requirements。`pip wheel --no-cache-dir --no-deps --no-build-isolation` 构建 `hdl_x-0.1.0-py3-none-any.whl` 成功；wheel 包含 verification 模块、3 个 Jinja2 templates，METADATA 含 `Requires-Dist: pyGHDL==6.0.0`。
- **Remaining risks:** 本机没有 GHDL CLI/Icarus，因此新增差分场景尚未在真实双 simulator 环境执行；没有 Yosys/SymbiYosys 形式等价结果。完整 IEEE `std_logic` 9-state、clock/reset X/Z transition、time-zero initial state、跨文件 library/package/configuration、复杂宽度/常量求值仍不在 v0.1 保证内。pyGHDL/libghdl 仍有 process-global/private-IIR 生命周期风险，由锁与回归约束。
- **Release decision:** 代码、测试门禁、wheel metadata 与文档已达到 v0.1 technical candidate 条件；但仓库仍没有项目 LICENSE/`pyproject.toml` license metadata，且 pyGHDL 为 GPL-2.0-or-later。公开再分发前必须由项目所有者完成许可证兼容性决定；在该决定前不能宣称法律/分发层面的最终 release-ready。

## v0.1.0 Release Readiness Audit

- **Scope:** 仅检查发布门禁、wheel smoke、外部等价工具和许可证/分发边界；未修改 IR、lowering、generator 或 Verilog 输出。
- **External tools:** 当前 PATH 中 `ghdl`、`iverilog`、`vvp`、`yosys`、`sby`/`symbiyosys` 均不存在。普通 equivalence run 明确得到 2 skipped；`--require-semantic-equivalence` 在 collection 前以 exit 1 拒绝发布，并列出 `ghdl, iverilog, vvp`，不会把 skip 当作 pass。
- **Final validation:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --basetemp build\pytest-v01-final-gate-20260818` → **267 passed, 2 skipped in 9.30s**；真实 GHDL integration **129/129 passed, 0 skipped, pyGHDL 6.0.0**；两个 skip 仅为本机尚未具备独立 simulator 的组合与 clock/reset/enable 差分测试。Ruff、compileall、`pip check` 和 `git diff --check` 均通过；`git diff -- tests/golden` 为空。
- **CI gate:** 新增 Ubuntu 24.04 semantic-equivalence job，固定 GHDL 6.0.0/mcode；`actions/checkout`、`actions/setup-python`、`ghdl/setup-ghdl` 均固定到审核过的完整 commit SHA。job 校验官方 Linux CPython 3.13 pyGHDL wheel SHA-256，安装 Icarus/VVP，执行要求的 pytest 命令，并额外强制终端汇总为 `passed=2, failed=0, skipped=0`。由于本轮按要求未 commit/push，该远程 job 尚未实际执行，不能把它记录为等价测试通过。
- **Wheel audit:** 最终构建生成 `hdl_x-0.1.0-py3-none-any.whl`，SHA-256 `ccea7a955a65d1f7f578062e2c305e4fe367137c9e13c024645ed179df3676b3`。archive 含 CLI/GUI entry points、verification 模块和 3 个 Jinja2 templates；不含测试 fixture，也不捆绑 pyGHDL/libghdl。fixture/golden 属于源码测试资产。METADATA 精确声明 `pyGHDL==6.0.0`，但项目 License 字段为空。
- **Isolated wheelhouse smoke:** `scripts/release_wheel_smoke.py` 下载并校验官方 Windows CPython 3.13 pyGHDL wheel，构建包含全部运行依赖及 SHA256SUMS 的 wheelhouse，以 `system_site_packages=False` 新建 venv，并仅用 `--no-index --find-links` 安装。CLI、doctor、`pip check` 与真实 `m2_simple_and.vhd` 转换均通过；pyGHDL wheel SHA-256 `624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839`；生成文件与 committed golden 均为 SHA-256 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`，逐字一致。该门禁现在是真正隔离完成，不依赖宿主 Python 包。
- **Distribution audit:** Python wheel 只依赖、但不包含 pyGHDL；PyInstaller spec 则明确收集 pyGHDL metadata、DLL 和 VHDL 标准/IEEE 库。仓库没有 LICENSE，`pyproject.toml` 也没有项目 license metadata。在项目所有者确认许可证兼容性、第三方 notice/对应源码义务与 EXE 分发方式前，不批准正式 `v0.1.0`。
- **Verdict:** 当前适合作为 `v0.1.0-rc1` 技术候选。正式 `v0.1.0` 仍需让新增 CI 或其他独立 GHDL CLI/Icarus 环境中的两项差分测试零 skip 通过，并由所有者完成许可证/分发决定；隔离 wheelhouse smoke 已不再是阻塞项。

## v0.1.1 Release Preparation — License Complete, Remote CI Pending

- **Owner decision:** 项目所有者确认为 `Copyright (c) 2026 rh`，HDL-X 自有源码采用 MIT，发布源码和纯 Python wheel，暂缓 PyInstaller EXE；要求 CycloneDX SBOM，不要求 wheel/源码签名，也不要求本次外部法律审查。该记录不作 MIT 与第三方许可证之间的法律结论。
- **Version decision:** 远端已有不可覆盖的公开 `v0.1.0` tag/Release；项目所有者选择保留旧发布并将本次发布版本升级为 `v0.1.1`，未移动或删除旧 tag。
- **License materials:** 新增最终 `LICENSE`、根目录/Release 附件共用的 `THIRD_PARTY_NOTICES`、CycloneDX 1.6 `SBOM.cdx.json`；`pyproject.toml` 使用 `License-Expression: MIT`、作者 `rh` 和 `License-File: LICENSE, THIRD_PARTY_NOTICES`。SBOM 覆盖最终 Windows CPython 3.13 隔离 wheelhouse 的 20 个组件（包含 Typer 内嵌的 Click），并明确 HDL-X wheel 不包含 pyGHDL、v0.1.1 不发布 EXE。
- **Local tests:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --basetemp build\pytest-v011-release-20260818` → **267 passed, 2 skipped in 9.45s**；GHDL integration **129/129 passed, 0 skipped, pyGHDL 6.0.0**。两项 skip 只因本机缺少 `ghdl`, `iverilog`, `vvp`，未计为等价通过。Ruff、compileall、`pip check`、`git diff --check` 均通过，`git diff -- tests/golden` 为空。
- **Final isolated wheelhouse:** 新建 `system_site_packages=False` venv，仅从新建完整 wheelhouse 以 `--no-index` 安装；CLI、doctor、真实 GHDL 转换、`pip check` 和 golden 字节比较全部通过。最终 smoke wheel SHA-256 `d6e1ef767d1ba70e6f72682b6aa3f0582a02e6c5a220f1d5397b1a13012fdb0c`；官方 pyGHDL wheel `624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839`；生成文件与 golden 均为 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`。SBOM SHA-256 `7b7c99c89fad6f5ba17c60cb5c53f7647eb182f45ae57c7e9ddb3eefb90c233b`。
- **Pending gate:** `.github/workflows/release-gates.yml` 仍须在远端实际执行，并明确得到 semantic equivalence `passed=2, failed=0, skipped=0`。在读取到该结果前，不创建 `v0.1.1` tag 或 GitHub Release。

## v0.2 SystemVerilog → Verilog-2001 MVP — Local Implementation Complete

- **Baseline and scope:** 以公开 `v0.1.1` / `7bf9785` 为干净基线；未修改 Canonical IR schema、公开 `ConversionResult.design` 节点类型或任何已跟踪 VHDL golden。设计、支持矩阵与停止条件记录在 `V0_2_SYSTEMVERILOG_MVP.md`。
- **Real frontend:** 精确固定 optional `pyslang==11.0.0`，实际调用 Slang `SyntaxTree` 和 `Compilation`。所有 Slang 对象在 `parser/slang` 内序列化为纯 Python Raw IR；Canonical IR、semantic lowering、Verilog lowering 和 generator 均不依赖或持有 pyslang 类型。
- **Implemented subset:** 单文件 module/ANSI ports；parameter 与受限 localparam 内联；logic/reg/wire、单比特/一维 packed vector；assign；always_comb/always_ff；blocking/nonblocking scheduling；if/else、case/default；posedge/negedge；同步/异步及高/低有效 reset；named/positional parameter/port connection；symbolic width 与 parameter expression；大小写敏感名称。
- **Conservative diagnostics:** interface/modport、program/package/class/clocking、typedef/复杂类型、普通 always/always_latch、initial/final/assertion、generate 和其他未支持结构产生 `HDLX-SV-*` 结构化错误。two-state `bit/int` 数据对象、initializer、复合 event 和无法安全关联的注释不会静默降级；strict 失败，best-effort 只可对注释省略返回 warning。
- **Lowering boundary:** pipeline 为 SystemVerilog 选择大小写敏感 identifier lowering；driver/storage 与过程赋值目标操作符由 `VerilogLowering` 写入 `VerilogRenderIR`。renderer 不再读取 deprecated Canonical `AssignmentKind` 决定文本操作符；旧字段、JSON 和 generator facade 仍兼容。
- **Real frontend tests:** `python -m pytest tests/integration -m slang_integration -q -ra -p no:cacheprovider --require-slang-integration --basetemp build\pytest-v02-slang-final2` → **30 passed, 151 deselected**；Slang integration **30/30 passed, 0 skipped, pyslang 11.0.0**。
- **Full regression:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --require-slang-integration --basetemp build\pytest-v02-full-final3` → **311 passed, 6 skipped in 12.98s**；GHDL integration **129/129 passed, 0 skipped**。Slang marker 汇总为 34/34，其中 30 个真实 frontend tests passed，4 个外部等价场景因工具缺失 skipped。
- **Skip accounting:** VHDL differential **0 passed, 2 skipped**，缺少 `ghdl`, `iverilog`, `vvp`；SystemVerilog compile/differential **0 passed, 4 skipped**，缺少 `iverilog`, `vvp`。`--require-systemverilog-equivalence` 实测 exit 1 并列出缺失工具，未把 skip 计为 pass。
- **Lowering/golden compatibility:** 旧 generator facade、新 pipeline lowering、6 个 VHDL M2 golden 与真实 SystemVerilog lowering 专项 → **35 passed**；GHDL 26/26、Slang 2/2 均零跳过。`git diff --exit-code -- tests/golden` 与 `git ls-files --modified -- tests/golden` 均为空；最小 VHDL CLI 输出 SHA-256 仍为 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`。
- **Independent compile/simulation evidence:** 本机 Icarus/Verilator 不可用，但 Vivado 2023.2 `xvlog/xelab/xsim` 可用。组合、时序及 signed/reg declaration 的 SystemVerilog 源与对应生成 Verilog 均编译成功；进一步在四个隔离 workdir 运行同一 testbench，组合源/目标 32/32 traces、clock/reset/enable 时序源/目标 6/6 traces 逐项一致。XSim elaboration 通过官方 `--timescale 1ns/1ps` 给无 timescale 的设计模块设置默认值；没有修改源或 golden。该结果是补充行为证据，但不把 Icarus pytest skip 或未运行的远端 CI 改写成通过。
- **Quality:** `python -m ruff check .`、`python -m compileall -q src tests packaging\windows`、`python -m pip check`、`git diff --check` 全部通过。
- **Wheel audit:** 最终本地构建 `hdl_x-0.1.1-py3-none-any.whl` 成功，SHA-256 `7b73ae52daf052dec99f9d5c72a6fc8f5ef17fb957a616c914855446a4f452b6`；66 entries、3 个 Jinja2 templates，包含 HDL-X Slang adapter/backend 但不包含第三方 pyslang payload。metadata 精确声明 `Requires-Dist: pyslang==11.0.0; extra == "systemverilog"`。
- **Isolated core-wheel smoke:** 以 `system_site_packages=False` 新建 venv，复用 18 个已审核本地依赖 wheels 并用 `--no-index` 安装当前候选 wheel。`pip check`、doctor、真实 VHDL conversion 与 golden 字节比较通过；未安装 pyslang 时 SystemVerilog 请求 exit 1、返回 `HDLX-SV-FRONTEND-UNAVAILABLE` 且不创建输出，证明 optional extra 不影响核心 VHDL 路径。
- **CI and release status:** `.github/workflows/release-gates.yml` 新增 Ubuntu 24.04 `systemverilog-mvp` job，固定 actions commit、pyslang 11.0.0 wheel URL/SHA-256，安装 Icarus/VVP，先强制真实 Slang frontend `30/30 passed, 0 skipped`，再强制编译/差分 `4/4 passed, 0 skipped`。本轮没有 commit/push 授权，该 job 尚未远端执行；不得声称 CI 或差分等价已通过。
- **Distribution material:** `THIRD_PARTY_NOTICES` 已加入 optional pyslang 11.0.0/MIT 的来源和 wheel license 路径；当前 `SBOM.cdx.json` 明确仍是 v0.1.1 历史快照。任何 v0.2 正式发布前必须按最终 wheelhouse 重建 SBOM；v0.2 MVP 不发布 EXE。
- **Remaining semantic risks:** `always_comb` time-zero 调度、clock/reset X/Z edge、复杂 sizing/signedness/unsized literal、two-state 数据对象、跨文件 compilation unit/package/include、generate 和复杂类型不在等价承诺内。同步 reset 分类只识别文档列明的顶层 if/else 与 reset 名称约定；未命中时保留普通 clocked if/else。内部注释只有在能安全关联时保留。

## 0.2.0-rc1 Release Candidate Preparation

- **Version decision:** 为避免与已发布 `v0.1.1` 混淆，正式候选显示版本使用 `0.2.0-rc1`，PEP 440 / wheel metadata 使用等价的 `0.2.0rc1`；本阶段不创建 tag 或 GitHub Release。
- **Compatibility boundary:** 候选继续冻结 `v0.1.1` 的 VHDL → Verilog 行为、公开 Canonical IR/JSON、`ConversionResult.design` 节点类型、旧 generator facade 与 tracked VHDL golden；仅扩展 SystemVerilog frontend、诊断、发布脚本、CI 和文档。
- **Semantic diagnostics:** `always_comb` time-zero 与 stable-0/1-only edge 分别返回 `HDLX-SV-ALWAYS-COMB-TIME-ZERO`、`HDLX-SV-EDGE-XZ` warning；未命中 reset 命名约定的 `clear/clr/por` 返回 `HDLX-SV-RESET-UNCLASSIFIED` warning。mixed signedness、跨文件 include/compilation unit 与 generate 分别以 `HDLX-SV-SIGNED-SIZING`、`HDLX-SV-COMPILATION-UNIT`、`HDLX-SV-GENERATE` 拒绝，best-effort 不会静默放行。
- **Frontend regression:** 新诊断和负面 fixture 复用现有测试函数，不改变 release gate 的收集数量；本地真实 Slang integration 已重新得到 **30 passed, 0 skipped, pyslang 11.0.0**。
- **Candidate packaging:** 最终隔离 smoke 以 `system_site_packages=False` 新建 venv，只从完整 wheelhouse 用 `--no-index` 安装 `hdl-x[systemverilog]==0.2.0rc1`；CLI、doctor、pip check、真实 VHDL/SystemVerilog conversion 与两份 golden 字节比较均通过。wheel 为 `hdl_x-0.2.0rc1-py3-none-any.whl`（67 entries、3 templates），SHA-256 `062db304cebcfc07b95dbc0ba85c734c37d0edaa63bbf5c818262d5202388197`；官方 pyGHDL wheel `624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839`；官方 pyslang wheel `b9cae2cc3d856bf7e52620a74cf9e2bb687c280ecccf70fbb63e49e690e77a47`。VHDL generated/golden 均为 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`；SystemVerilog generated/golden 均为 `137447ebe3e06115bccb2dd941977270b20ec400001b51bb7bcee778efabdb83`。
- **Local final gates:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --require-slang-integration` → **313 passed, 6 skipped**；GHDL integration **129/129 passed, 0 skipped**。6 个 skip 仅为本机缺少 `ghdl`, `iverilog`, `vvp` 的 2 个 VHDL 和 4 个 SystemVerilog 外部等价场景，未计为 pass。Ruff、compileall、pip check、`git diff --check` 和相对 `v0.1.1` 的 VHDL golden 0 diff 均通过。
- **SBOM:** 从上述最终 wheelhouse 生成 CycloneDX 1.6，共 21 个 project/dependency components；项目版本为 `0.2.0rc1`，active extra 为 `systemverilog`，`hdl-x` 依赖关系明确包含 `pyslang@11.0.0`。SBOM SHA-256 `aad33538d667f414d2458cb6b393e3ee8a802cd1ed1ac214aa47f279c21d5339`。
- **Remote status:** 候选代码提交 `3f4c29911f0a82b313f8201ce4e930a592abb084` 的真实 GitHub Actions [run 32639207648](https://github.com/ronghui0411/HDL-X/actions/runs/32639207648) 已通过：Slang `30/30`、SystemVerilog equivalence `4/4`、VHDL semantic equivalence `2/2` 均为 `failed=0, skipped=0`；完整质量 job 为 `319 passed`，GHDL integration `129/129`，VHDL golden 0 diff，isolated wheelhouse smoke 成功。本阶段仍未创建 tag 或 GitHub Release。

## 0.2.0 Release Freeze Hardening

- **Verified baseline:** 本轮开始时 `main`、`origin/main` 和声明基线 `2a38b2f70382a27d57f3d1379fa003f68c9d1d88` 一致，ahead/behind 0/0 且工作区干净；远端 [run 32639425584](https://github.com/ronghui0411/HDL-X/actions/runs/32639425584) 的 head SHA 一致、四个 RC job success，且不存在 v0.2 tag/Release。该证据只作为 RC 基线，不冒充本轮最终 CI。
- **Semantic hardening:** dependency-free `always_comb` 以 `HDLX-SV-ALWAYS-COMB-NO-TRIGGER` 拒绝；macro-only include 也以 `HDLX-SV-COMPILATION-UNIT` 拒绝；unsigned integer parameter 以 `HDLX-SV-PARAMETER-SIGNEDNESS` 拒绝；异步 reset event/条件 polarity 不一致继续以 `HDLX-SV-ASYNC-RESET-EVENT` 拒绝。上述 unsafe 情形 strict/best-effort 均失败。
- **Positive evidence:** 新增 signed 参数表达式、异步高有效 reset、同步低有效 reset 的真实 Slang、golden、Verilog-2001 编译和差分场景；显式/隐式 generate 局部信号和 compilation-unit 边界有真实 Slang 负面 fixture。本地真实 Slang integration 已得到 **41 passed, 0 skipped, pyslang 11.0.0**。
- **Architecture boundary:** 递归验证 Raw/Canonical 全图不含 pyslang 对象；Verilog lowering 现在把 `wire/reg/integer` storage 与 `=`/`<=` 一起写入 `VerilogRenderIR`，renderer/Jinja2 不再从 Canonical compatibility 字段推导 storage。新 storage 字段保留旧 positional `assignment_operators` 的第三参数位置，并有兼容测试；Canonical IR/JSON 未修改。
- **Version freeze:** `pyproject.toml` 和 wheel smoke 期望值提升为正式 `0.2.0`；workflow 更新为强制 Slang **41/41** 和 SystemVerilog compile/equivalence **8/8**，所有 action 仍固定完整 commit SHA。当前没有创建 tag 或 Release。
- **Local final gates:** `python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --require-slang-integration` → **331 passed, 10 skipped**；GHDL integration **129/129 passed, 0 skipped**。2 个 VHDL equivalence 和 8 个 SystemVerilog equivalence 仅因本机缺少 `ghdl`/`iverilog`/`vvp` 跳过，未计为 pass。真实 Slang integration 独立门禁为 **41/41 passed, 0 skipped**。Ruff、compileall、pip check、diff check、相对 v0.1.1 的 VHDL golden 0 diff 和已有 SV golden 0 diff 全部通过。
- **Final isolated wheelhouse:** `system_site_packages=False` venv 只从完整 wheelhouse 以 `--no-index` 安装 `hdl-x[systemverilog]==0.2.0`；CLI、doctor、pip check、真实 VHDL/SV conversion 与 golden 字节比较通过。wheel `hdl_x-0.2.0-py3-none-any.whl` 为 67 entries、3 templates、2 entry points、2 license files，SHA-256 `834c447b3bc95bf256072f03c924a375c89ff3443aaebb80ad0c8a7ac1f1d5dc`；pyGHDL/pyslang wheels 分别为 `624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839`、`b9cae2cc3d856bf7e52620a74cf9e2bb687c280ecccf70fbb63e49e690e77a47`。VHDL 与 SV generated/golden 分别保持 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`、`137447ebe3e06115bccb2dd941977270b20ec400001b51bb7bcee778efabdb83`。
- **Final SBOM:** 从上述 wheelhouse 重建 CycloneDX 1.6，共 21 个 project/dependency components；项目 `hdl-x@0.2.0` 明确依赖 `pyslang@11.0.0`，active extra 为 `systemverilog`。SBOM SHA-256 `d38f31295d0b87b8ebeb80233dcbfd967df3ad6b76a0bfde0c4ca1a3babd9f9d`。
- **Pending evidence:** 普通 commit/push 与真实远端零跳过 CI 尚待完成；在 Slang 41/41、SystemVerilog equivalence 8/8、VHDL semantic equivalence 2/2、完整质量与 isolated smoke 四个 job 全部 success 前，不请求发布授权，不创建 tag/Release。
