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
- **Known technical debt:** pyGHDL/libghdl 是 process-global state，当前以锁、arena reset 和私有 design-file access 隔离；generate fallback 依赖已验证的 6.0.0 API 边界；comment end spans 不完整；没有通用 VHDL constant evaluator 或多文件 project/library model；项目级 LICENSE/`pyproject.toml` license metadata 尚未选定，分发前还需结合 pyGHDL GPL-2.0-or-later 完成许可决策。
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
