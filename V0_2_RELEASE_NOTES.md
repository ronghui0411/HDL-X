# HDL-X 0.2.0 Release Notes（Pre-Tag Freeze）

项目 metadata 已从 `0.2.0rc1` 提升为正式 `0.2.0`，预期 wheel 文件名为
`hdl_x-0.2.0-py3-none-any.whl`。本文件记录正式发布冻结内容；当前尚未创建 `v0.2.0` tag
或 GitHub Release，必须等待项目所有者明确说“允许发布”。

## 主要变化

- 新增真实 `pyslang==11.0.0` / Slang SystemVerilog frontend，可选安装边界为
  `hdl-x[systemverilog]`。
- 支持冻结的单文件、可综合 SystemVerilog 子集，并输出 Verilog-2001。
- 保持 v0.1.1 的 VHDL → Verilog 文本、公开 Canonical IR/JSON、
  `ConversionResult.design` 和旧 generator facade 不变。
- pipeline 拥有 semantic/Verilog lowering；`VerilogRenderIR` 承载 storage 与过程赋值操作符，
  renderer/Jinja2 只格式化已完成 lowering 的结构。
- release gate 强制真实 Slang integration、SystemVerilog 编译/差分、VHDL 回归、完整质量
  检查和隔离 wheelhouse smoke；任何 skip 都不能计为通过。

## 冻结后的语义风险与处理

| 风险 | v0.2.0 处理 |
| --- | --- |
| `always_comb` time-zero | 有读取依赖的组合过程降为 `always @(*)`，返回 `HDLX-SV-ALWAYS-COMB-TIME-ZERO` warning，差分测试在稳定输入后采样；若能证明没有任何读取依赖，目标 `@(*)` 没有触发源，以 `HDLX-SV-ALWAYS-COMB-NO-TRIGGER` 拒绝，best-effort 同样失败。 |
| clock/reset X/Z edge | 只承诺稳定 0/1 跳变；edge-triggered `always_ff` 返回 `HDLX-SV-EDGE-XZ` warning，X/Z transition 不计入等价声明。同步/异步、高/低有效 reset 的稳定边界由差分测试覆盖。 |
| signed/unsigned sizing | 同 signedness packed vector、signed `parameter int` 及已支持参数表达式保留并差分；mixed signed/unsigned 以 `HDLX-SV-SIGNED-SIZING` 拒绝，`parameter int unsigned` 以 `HDLX-SV-PARAMETER-SIGNEDNESS` 拒绝。复杂 cast、unsized literal 和 context-determined sizing 仍不作等价声明。 |
| compilation unit/package/include | 只支持单文件；任何 include directive（含仅提供宏的 `.svh`）以 `HDLX-SV-COMPILATION-UNIT` 拒绝，package/import 和多 compilation-unit flow 继续结构化拒绝。 |
| generate 层次/局部信号 | v0.2 MVP 不接受显式或隐式 generate；真实 Slang syntax node 以 `HDLX-SV-GENERATE` 拒绝，不展开、不丢弃局部声明或层次。 |
| reset 分类 | 支持顶层 `if/else`、稳定 event/条件 polarity 的同步/异步高低有效 reset。异步 event 与条件 polarity 不一致以 `HDLX-SV-ASYNC-RESET-EVENT` 拒绝；`clear/clr/por` 等未命中命名约定时保留普通 clocked `if/else` 并返回 `HDLX-SV-RESET-UNCLASSIFIED` warning。 |

warning 表示综合结构可转换但完整语言级仿真声明受限；结构化 error 表示无法证明安全，
`--best-effort` 也会失败。这些变更不改变 v0.1.1 VHDL golden。

## 分发与发布门禁

- 发布源码和纯 Python wheel；不构建、不发布 PyInstaller EXE。
- HDL-X wheel 不捆绑 pyGHDL/libghdl 或 pyslang/Slang；前者是精确核心依赖，后者是精确
  `systemverilog` optional extra。
- CycloneDX SBOM 必须来自最终隔离 wheelhouse，并包含 `pyGHDL==6.0.0`、
  `pyslang==11.0.0`、`hdl-x==0.2.0` 及 wheel SHA-256。
- 最终远端门禁必须实际得到 Slang `41 passed, 0 skipped`、SystemVerilog compile/equivalence
  `8 passed, 0 skipped`、VHDL semantic equivalence `2 passed, 0 skipped`、VHDL golden 0 diff、
  完整质量与 isolated wheelhouse smoke 成功。
- 达到上述技术门禁后仍不自动创建 tag/Release；等待项目所有者明确发布授权。
