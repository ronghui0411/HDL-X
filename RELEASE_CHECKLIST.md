# HDL-X v0.3.0-rc1 Release Checklist

本清单是候选发布门禁，不替代法律意见。`v0.2.0` 是不可变稳定基线；任何未勾选的
“阻塞”项都表示尚未达到创建 `v0.3.0-rc1` tag 的条件。项目所有者尚未授权创建任何
v0.3 tag 或 GitHub Release。

## 兼容与架构门禁

- [x] 基线固定为 `v0.2.0` / `f283854d2d059e1bc54174d7f9509430c984bbe7`，不改写其
  tag、Release、wheel、SBOM 或历史制品。
- [x] Canonical IR、公开 Python API、JSON 字段和 deprecated 兼容字段未改变。
- [x] pyslang 对象只存在于 `parser/slang`；Raw IR 离开 frontend 后是纯 Python 数据。
- [x] pipeline 拥有 VHDL semantic boundary 与 `VhdlLowering`；`VhdlRenderIR` 承担目标
  entity/architecture/signal/process/generic/instance 决策，Jinja2 只格式化。
- [x] VHDL→Verilog 与 SystemVerilog→Verilog 的已有 API/golden 契约保持不变。
- [x] unsafe Verilog 构造在 strict 和 best-effort 中都以结构化 `HDLX-V2V-*` 诊断失败，
  不静默删除 RTL。
- [x] 最终相对 `v0.2.0` 审计确认 `tests/golden` 逐字零差异。

## Verilog→VHDL MVP 证据

- [x] 真实 pyslang 11.0.0 覆盖 module/ANSI ports、parameter、wire/reg/integer、packed
  signed/unsigned、assign、组合/时序 always、if/case、reset、instance 与必要 generate。
- [x] 真实 pyGHDL/libghdl 6.0.0 分析全部正向 VHDL golden，缺失 runtime 不允许 skip。
- [x] blocking 组合赋值通过 process-local VHDL variable 保留 read-after-write；时序
  nonblocking 映射为 clock/reset process 中的 signal assignment。
- [x] time-zero、X/Z edge、未初始化状态、显式 X 和 unsized sizing 边界均有明确 warning；
  tri-state、mixed signed sizing、隐式截断、跨文件/include/package、歧义 reset/event、
  多驱动及不安全 generate 均有负面测试和稳定诊断码。
- [x] 本机已分别用 pyGHDL 分析 7 组生成 VHDL DUT+TB，并用 pyslang 编译 7 组原始
  Verilog DUT+TB；这不是双 simulator trace 等价通过声明。
- [x] Ubuntu 24.04 真实 CI 中 Verilog→VHDL 差分为
  `passed=7, failed=0, skipped=0`。

## 回归与质量门禁

- [x] 完整 pytest 在具备外部工具的 CI 中为 **403 passed, 0 skipped**。
- [x] 真实 GHDL integration **146/146 passed, 0 skipped**。
- [x] 真实 Slang integration **96 passed, 0 skipped**。
- [x] VHDL semantic equivalence 为 **2 passed, 0 skipped**。
- [x] SystemVerilog compile/equivalence 为 **8 passed, 0 skipped**。
- [x] Ruff、compileall、pip check 与 `git diff --check` 全部通过。
- [x] 本机缺少 standalone `ghdl`、`iverilog`、`vvp` 时，普通入口明确列出 skip，
  三个 `--require-*equivalence` 门禁必须非零失败；不得把这些 skip 计为 pass。

## wheel、SBOM 与分发材料

- [x] 构建 `hdl_x-0.3.0rc1-py3-none-any.whl`；metadata 与 `pyproject.toml`
  版本、核心 `pyGHDL==6.0.0`、`systemverilog`/`verilog` 的 `pyslang==11.0.0` 一致，
  wheel SHA-256 为 `eab235700139c0932008fa184f98e26bb2d73564749fbecd0f5393d90defebe5`。
- [x] wheel 共 78 entries，包含 6 个 Jinja2 模板、CLI/GUI entry point、`LICENSE` 和
  `THIRD_PARTY_NOTICES`，且不包含 pyGHDL/libghdl/pyslang payload。
- [x] 在 `system_site_packages=False` 的全新 venv 中，仅从完整 wheelhouse
  以 `--no-index` 安装 `hdl-x[systemverilog,verilog]`；CLI、doctor、pip check、真实
  VHDL→Verilog、SystemVerilog→Verilog、Verilog→VHDL 转换和三份 golden 字节比较通过。
- [x] 已输出 HDL-X、pyGHDL、pyslang wheels 与三份生成文件的 SHA-256，且三组 generated/golden 哈希分别一致。
- [x] 从最终 wheelhouse 重建 CycloneDX 1.6 `SBOM.cdx.json`，项目版本为
  `0.3.0rc1`，active extras 为 `systemverilog,verilog`，并显式依赖 pyslang 11.0.0；
  SBOM SHA-256 为 `4f97a6b22ea7dbe062b8237bb5a7fe2785317457956cdfc664b94ba08588d82c`。
- [x] `THIRD_PARTY_NOTICES` 记录源码、纯 Python wheel 与暂缓 PyInstaller EXE 的不同
  分发边界；v0.3 候选不构建、不发布 EXE。
- [x] README、`V0_3_VERILOG_TO_VHDL_MVP.md`、本清单、开发日志、wheel metadata、
  SBOM 和最终校验值保持一致。

## CI 与发布动作

- [x] `.github/workflows/release-gates.yml` 使用 Ubuntu 24.04、固定完整 action commit、
  GHDL 6.0.0、审核过的 pyGHDL/pyslang wheel URL/SHA-256 和 Icarus/VVP。
- [x] workflow 分离并强制 VHDL semantic、SystemVerilog、Verilog→VHDL、完整质量和
  isolated wheelhouse smoke 门禁，不允许 skipped 冒充 passed。
- [x] 候选代码 commit `f1082152bc7e511d42021d5572305982a5f49013` 已普通 push；真实
  GitHub Actions run `32685609281` 的 5 个 job 全部 success，且日志中的精确
  passed/failed/skipped 计数与本清单一致。
- [ ] 只有上述门禁全部满足并获得项目所有者的单独发布授权后，才允许创建
  `v0.3.0-rc1` tag 或 GitHub Release；不得 force-push。

## 最终验证命令

```powershell
python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration --require-slang-integration
python -m pytest tests/equivalence -q -ra --require-semantic-equivalence --require-systemverilog-equivalence --require-verilog-to-vhdl-equivalence
python -m ruff check .
python -m compileall -q src tests scripts packaging/windows
python -m pip check
python scripts/release_wheel_smoke.py --workspace <new-empty-directory>
```