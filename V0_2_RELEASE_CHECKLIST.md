# HDL-X 0.2.0-rc1 SystemVerilog MVP Release Checklist

本清单描述 v0.2 正式候选的技术门禁。人类可读候选版本为 `0.2.0-rc1`，PEP 440 / wheel
metadata 为 `0.2.0rc1`。它与已发布 `v0.1.1` 明确区分；在本清单全部完成前不得创建
v0.2 tag 或 GitHub Release。v0.1.1 的历史证据继续保留在 `RELEASE_CHECKLIST.md`。

## 版本与兼容性

- [x] 使用 `v0.1.1` / `7bf9785d29410360979ca56c0563f45d9467d1c2` 作为稳定基线。
- [x] 候选版本确定为显示形式 `0.2.0-rc1`、PEP 440 形式 `0.2.0rc1`。
- [x] 不删除或改名公开 Python API，不改变 `ConversionResult.design` 的公开节点类型。
- [x] 不改变 Canonical IR JSON 字段；deprecated `AssignmentKind`、`DriverKind` 继续保留。
- [x] 不修改已有 VHDL generator、lowering、Canonical IR 或 tracked VHDL golden。
- [x] 最终完整 v0.1.1 回归和真实 GHDL integration 零跳过通过。
- [x] tracked VHDL golden 与 `v0.1.1` 逐字一致（0 diff）。

## 真实 SystemVerilog frontend

- [x] 只通过精确 optional dependency `pyslang==11.0.0` 启用 SystemVerilog 输入。
- [x] backend 实际调用 Slang `SyntaxTree` 和 `Compilation`；不是正则或 fixture parser。
- [x] Slang 对象只存在于 `parser/slang` 私有边界；Raw/Canonical/lowering/generator 不持有
  `pyslang` 类型。
- [x] `--require-slang-integration` 在 runtime 缺失、版本不精确、零选择或 skip 时失败。
- [x] 本地真实 frontend gate 保持 `30 passed, 0 skipped`，没有为新增负面覆盖增加收集数。
- [ ] 远端 `systemverilog-mvp` 实际得到 Slang `30 passed, 0 skipped`。

## 语义边界与负面门禁

- [x] `always_comb` → `always @(*)` 不改变输出，但返回
  `HDLX-SV-ALWAYS-COMB-TIME-ZERO` warning。
- [x] edge-triggered `always_ff` 对 X/Z transition 返回 `HDLX-SV-EDGE-XZ` warning；只承诺
  稳定 0/1 跳变。
- [x] Slang signedness conversion 与 mixed signed/unsigned expression 以
  `HDLX-SV-SIGNED-SIZING` 拒绝；best-effort 同样失败。
- [x] 跨文件 include/compilation-unit 以 `HDLX-SV-COMPILATION-UNIT` 拒绝。
- [x] SystemVerilog generate 以 `HDLX-SV-GENERATE` 拒绝，不展开、不静默省略。
- [x] 未命中 rst/reset 命名约定的 `clear/clr/por` 疑似复位保留普通 clocked if/else，并
  返回 `HDLX-SV-RESET-UNCLASSIFIED` warning。
- [x] two-state `bit/int` 数据对象、initializer、复杂类型和 testbench-only construct
  继续结构化拒绝；best-effort 不跳过 RTL/结构节点。
- [x] 风险和承诺范围记录在 `V0_2_RELEASE_NOTES.md`。

## 编译、差分与 CI

- [x] workflow actions 使用审核后的完整 commit SHA；Ubuntu 固定为 24.04。
- [x] `systemverilog-mvp` 固定 pyslang Linux wheel URL/SHA-256，并安装 Icarus/VVP 与
  `libgnat-13`。
- [x] CI 文本门禁强制 Slang `30/30 passed, 0 skipped` 和 SystemVerilog compile/
  equivalence `4/4 passed, 0 skipped`。
- [ ] 远端 SystemVerilog compile/equivalence 实际得到 `4 passed, 0 skipped`。
- [ ] 远端 VHDL semantic equivalence 实际得到 `2 passed, 0 skipped`。
- [ ] 远端完整质量 job 与 isolated wheelhouse smoke 全部成功。

## 版本、wheel、SBOM 与 NOTICE

- [x] `pyproject.toml` 使用 `version = "0.2.0rc1"` 并精确声明
  `pyslang==11.0.0` optional extra。
- [x] README、候选 checklist、release notes、开发日志和 THIRD_PARTY_NOTICES 区分
  `0.2.0-rc1` 与历史 `v0.1.1`。
- [x] 最终 wheel metadata 为 `Version: 0.2.0rc1`，文件名为
  `hdl_x-0.2.0rc1-py3-none-any.whl`，模板与 entry points 完整。
- [x] clean wheelhouse smoke 在 `system_site_packages=False` venv 中只用 `--no-index`
  安装 `hdl-x[systemverilog]`，并完成 doctor、真实 VHDL/SystemVerilog 转换和 golden 比较。
- [x] 从上述候选 wheelhouse 重新生成 CycloneDX 1.6 `SBOM.cdx.json`。
- [x] SBOM 明确包含 `hdl-x==0.2.0rc1`、`pyGHDL==6.0.0`、`pyslang==11.0.0`、active
  `systemverilog` extra 依赖关系及 wheel SHA-256。
- [x] `THIRD_PARTY_NOTICES` 记录 pyslang/Slang MIT、pyGHDL/libghdl GPL-2.0-or-later、
  上游源码与“不捆绑进 HDL-X wheel”的边界。
- [x] 0.2.0-rc1 不构建、不发布 PyInstaller EXE。
- [x] 当前请求只授权 commit/push/等待 CI；暂不创建 tag 或 Release。

本地最终证据：完整 pytest `313 passed, 6 skipped`；GHDL integration `129/129 passed,
0 skipped`；6 个 skip 仅因本机缺少 `ghdl`/`iverilog`/`vvp`，没有计为等价通过。
Ruff、compileall、pip check、diff check 和 VHDL golden 0 diff 通过。最终候选 wheel SHA-256
为 `062db304cebcfc07b95dbc0ba85c734c37d0edaa63bbf5c818262d5202388197`；SBOM SHA-256
为 `aad33538d667f414d2458cb6b393e3ee8a802cd1ed1ac214aa47f279c21d5339`。

## 本地最终验证命令

```powershell
python -m pytest tests/integration -m slang_integration -q -ra --require-slang-integration
python -m pytest tests/equivalence/test_systemverilog_differential.py -q -ra --require-slang-integration --require-systemverilog-equivalence
python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --require-slang-integration
python -m ruff check .
python -m compileall -q src tests packaging/windows
python -m pip check
git diff --exit-code 7bf9785d29410360979ca56c0563f45d9467d1c2 -- 'tests/golden/m*.v'
python scripts/release_wheel_smoke.py --workspace <new-empty-directory>
```

## 验收判定

只有实际证据同时满足以下条件，才能报告 v0.2 MVP 验收完成：

```text
Slang integration: 30 passed, 0 skipped
SystemVerilog compile/equivalence: 4 passed, 0 skipped
VHDL regression: 0 golden diff
完整质量门禁：全部通过
SBOM：由 0.2.0rc1 候选 wheelhouse 重新生成并包含 pyslang 11.0.0
```

任何版本、SBOM、公开语义或远端结果不一致都必须暂停；不得创建 v0.2.0 tag。
