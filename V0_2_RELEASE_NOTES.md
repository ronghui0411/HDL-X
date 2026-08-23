# HDL-X 0.2.0-rc1 Release Notes

`0.2.0-rc1` 是 v0.2 的正式候选标识；Python/PEP 440 metadata 使用等价形式
`0.2.0rc1`，因此候选 wheel 文件名为 `hdl_x-0.2.0rc1-py3-none-any.whl`。它与已发布的
`v0.1.1` 明确区分。本文件不表示已经创建 tag 或 GitHub Release。

## 主要变化

- 新增真实 `pyslang==11.0.0` / Slang SystemVerilog frontend，可选安装边界为
  `hdl-x[systemverilog]`。
- 支持已冻结的单文件、可综合 SystemVerilog 子集，并继续输出 Verilog-2001。
- 保持 v0.1.1 的 VHDL → Verilog 文本、公开 Canonical IR/JSON、
  `ConversionResult.design` 和旧 generator facade 不变。
- release gate 分别强制真实 Slang integration、SystemVerilog 编译/差分、VHDL 回归、
  完整质量检查和隔离 wheelhouse smoke；任何 skip 都不能计为通过。

## 不扩大声明的语义风险

| 风险 | v0.2 候选处理 |
| --- | --- |
| `always_comb` time-zero | 降为 `always @(*)` 时保持综合组合结构，但不保证 time-zero 自动执行调度完全相同；每个转换返回 `HDLX-SV-ALWAYS-COMB-TIME-ZERO` warning，差分测试在输入稳定后采样。 |
| clock/reset X/Z edge | 只承诺稳定 0/1 跳变；每个 edge-triggered `always_ff` 返回 `HDLX-SV-EDGE-XZ` warning，X/Z transition 不计入等价声明。 |
| signed sizing | 同 signedness、已支持范围内的表达式保留；Slang 报告的 signedness conversion 与 adapter 可证明的 mixed signed/unsigned 二元表达式以 `HDLX-SV-SIGNED-SIZING` 拒绝，strict/best-effort 都不能放行。复杂 sizing、cast 和 unsized-literal 规则仍在支持范围外。 |
| 跨文件 compilation unit | 首个切片只支持单文件；跨文件 include 以 `HDLX-SV-COMPILATION-UNIT` 拒绝，package/import 和多 compilation-unit flow 不作等价声明。 |
| generate | SystemVerilog generate 不在首个切片内，依据真实 Slang syntax node 以 `HDLX-SV-GENERATE` 拒绝；不会展开或静默省略层次。 |
| reset 分类 | 只把已记录的顶层 `if/else` 与 `rst/reset` 命名形态分类为 Canonical reset。`clear/clr/por` 等疑似 reset 未命中时保留原 clocked `if/else` 文本行为，并返回 `HDLX-SV-RESET-UNCLASSIFIED` warning；不静默声称已识别 reset 语义。 |

这些诊断不改变生成的 v0.1.1 VHDL golden。warning 表示综合结构可转换、但语言级仿真
声明受限；结构化 error 表示无法证明安全，`--best-effort` 也会失败。

## 分发与候选门禁

- 发布源码和纯 Python wheel；不构建、不发布 PyInstaller EXE。
- HDL-X wheel 不捆绑 pyGHDL/libghdl 或 pyslang/Slang；前者是精确核心依赖，后者是精确
  `systemverilog` optional extra。
- CycloneDX SBOM 必须来自最终隔离 wheelhouse，并同时包含 `pyGHDL==6.0.0`、
  `pyslang==11.0.0` 及 `hdl-x==0.2.0rc1` 的依赖关系与 wheel SHA-256。
- 在远端门禁实际得到 Slang `30 passed, 0 skipped`、SystemVerilog 编译/等价
  `4 passed, 0 skipped`、VHDL golden 0 diff 和完整质量 job 成功前，不创建 v0.2 tag 或
  GitHub Release。
