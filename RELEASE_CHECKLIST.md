# HDL-X v0.1.1 Release Checklist

本清单是发布门禁，不替代法律意见。任何未勾选的“阻塞”项都表示只能生成候选构建，
不能把公开分发标记为正式 `v0.1.1`。

## 必需门禁

- [x] Python、pyGHDL/libghdl 与 backend 使用精确 `6.0.0` 版本规则。
- [x] 真实 in-process GHDL integration 被强制选择，缺失 runtime 时不允许 skip。
- [x] 完整 pytest、Ruff、compileall 与当前环境的 `pip check` 通过。
- [x] wheel 可构建，包含 CLI/GUI entry point、verification 模块和 3 个 Jinja2 模板。
- [x] wheel 本体不捆绑 pyGHDL/libghdl；metadata 明确声明 `pyGHDL==6.0.0`。
- [x] 在不启用 `--system-site-packages` 的全新虚拟环境，以完整 wheelhouse 和
  `--no-index` 安装 HDL-X、官方 pyGHDL 6.0.0 与全部运行依赖；CLI、doctor、真实转换、
  `pip check` 和 golden 字节比较全部通过，并输出 wheel/生成文件 SHA-256。
- [x] `--require-semantic-equivalence` 在 GHDL CLI/Icarus 缺失时以非零状态失败。
- [x] 添加 Ubuntu 24.04 semantic-equivalence CI job；GHDL 固定 6.0.0，Actions 固定到
  审核过的 commit，并强制检查 `passed=2, failed=0, skipped=0`。
- [ ] **阻塞：** 在具备 `ghdl`、`iverilog`、`vvp` 的独立环境运行
  `python -m pytest tests/equivalence -q -ra --require-semantic-equivalence`，组合与
  clock/reset/enable 两个场景均不得失败或跳过。
- [x] 项目所有者选择 MIT、确认 `Copyright (c) 2026 rh`，并完成第三方 notice、
  `pyproject.toml` license metadata，并确认与 pyGHDL/libghdl GPL-2.0-or-later 的
  技术分发边界记录；该记录不作法律结论。
- [x] v0.1.1 明确不发布 PyInstaller EXE；现有 `dist/HDL-X` 不得作为 Release 制品。
- [x] 生成 CycloneDX SBOM，并将 SBOM 与 `THIRD_PARTY_NOTICES` 同时保留在仓库根目录和
  GitHub Release 附件。

## 构建与验证命令

```powershell
python -m pytest -q -ra -p no:cacheprovider --require-ghdl-integration
python -m pytest tests/equivalence -q -ra -p no:cacheprovider --require-semantic-equivalence
python -m ruff check .
python -m compileall -q src tests packaging/windows
python -m pip check
python -m pip wheel --no-cache-dir --no-deps --no-build-isolation . --wheel-dir build/wheel-release
python scripts/release_wheel_smoke.py --workspace <new-empty-directory>
```

wheel smoke 脚本会拒绝复用既有目录，下载并校验审核过的官方 pyGHDL asset，构建完整
运行时 wheelhouse，再以 `system_site_packages=False` 的新 venv 和 `--no-index` 安装。
测试 fixture/golden 是源码测试资产，不属于运行时 wheel；wheel 内必须保留
`hdl_x/templates/**/*.j2`。

## 外部工具记录

每次候选构建都记录 `ghdl --version`、`iverilog -V`、`vvp -V`、`yosys -V` 与
`sby --version`（若存在）。Yosys/SymbiYosys 缺失不能冒充形式验证通过；当前 v0.1
行为等价 gate 的必需工具是 GHDL CLI、Icarus compiler 和 VVP runtime。

## 发布动作

- [x] 更新最终测试计数、skip 原因、wheel SHA-256 和构建平台。
- [x] 确认 `git diff -- tests/golden` 为空。
- [x] 从待发布 wheel 重跑最小真实转换并逐字比较 golden。
- [ ] 检查 wheel/sdist 文件清单与 metadata；测试 assets 仅需存在于源码归档。
- [ ] 完成上述门禁后，才允许创建 tag、GitHub Release 或上传公开制品。
