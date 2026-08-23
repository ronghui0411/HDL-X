# HDL-X 0.2.0 Release Freeze Checklist

本清单描述从已验收 `0.2.0-rc1` 推进到正式 `0.2.0` 的冻结门禁。PEP 440 / wheel metadata
使用 `0.2.0`。在所有技术门禁完成且项目所有者明确说“允许发布”前，不创建 `v0.2.0`
tag 或 GitHub Release；禁止 force push。v0.1.1 历史证据保留在 `RELEASE_CHECKLIST.md`。

## 基线与兼容性

- [x] 本轮开始时 `main`、`origin/main` 与声明基线
  `2a38b2f70382a27d57f3d1379fa003f68c9d1d88` 一致，ahead/behind 为 0/0，工作区干净。
- [x] GitHub Actions [run 32639425584](https://github.com/ronghui0411/HDL-X/actions/runs/32639425584)
  的 head SHA 与基线一致，四个 job 均 success；这是 RC 基线证据，不是本轮最终 CI。
- [x] 基线远端没有 v0.2 tag 或 GitHub Release。
- [x] 不删除或改名公开 Python API，不改变 `ConversionResult.design` 的公开节点类型。
- [x] 不改变 Canonical IR JSON 字段；deprecated `AssignmentKind`、`DriverKind` 继续保留。
- [x] 新 `VerilogRenderIR.storage_kinds` 位于旧 positional `assignment_operators` 参数之后，
  并有 v0.1.1 构造兼容回归测试。
- [x] 本轮最终 tracked VHDL golden 相对 `v0.1.1` 逐字一致（0 diff）；已有 SV golden 未修改，只新增两份有真实测试证据的冻结 golden。

## 真实 frontend、语义边界与架构

- [x] 精确 optional dependency `pyslang==11.0.0`；真实 `SyntaxTree`/`Compilation` 路径。
- [x] 递归检查 Raw 与 Canonical 全图，不含任何 `pyslang` 对象；Canonical、transformer、
  generator 没有 pyslang import。
- [x] `always_comb` 有读取依赖时给 `HDLX-SV-ALWAYS-COMB-TIME-ZERO` warning；无触发依赖以
  `HDLX-SV-ALWAYS-COMB-NO-TRIGGER` 拒绝。
- [x] X/Z edge 以 `HDLX-SV-EDGE-XZ` 限定稳定 0/1 承诺。
- [x] supported signed 参数表达式有真实 Slang/golden/差分覆盖；mixed signedness 与 unsigned
  integer parameter 分别以 `HDLX-SV-SIGNED-SIZING`、`HDLX-SV-PARAMETER-SIGNEDNESS` 拒绝。
- [x] 任何 include、package/import、多 compilation unit 结构化拒绝；macro-only include 有
  真实 Slang 负面 fixture。
- [x] 显式/隐式 generate 与局部信号以 `HDLX-SV-GENERATE` 拒绝，不静默展开或省略。
- [x] supported 同步/异步高低有效 reset 有真实 Slang/golden/差分覆盖；event/条件 polarity
  不一致以 `HDLX-SV-ASYNC-RESET-EVENT` 拒绝，未分类命名返回明确 warning。
- [x] pipeline/lowering 拥有 identifier、storage、blocking/non-blocking 决策；renderer 和
  Jinja2 不从 Canonical compatibility 字段重新推导目标语义。
- [x] strict/best-effort 的 unsafe 边界均有结构化诊断回归，best-effort 不静默丢弃 RTL。

## 本地与远端测试门禁

- [x] 本地真实 Slang integration：`41 passed, 0 skipped`（pyslang 11.0.0）。
- [ ] 具备 Icarus/VVP 的最终远端 SystemVerilog compile/equivalence：`8 passed, 0 skipped`。
- [ ] 最终远端 VHDL semantic equivalence：`2 passed, 0 skipped`。
- [x] 本地完整 pytest 331 passed、10 个外部模拟器缺失 skip；GHDL 129/129、Ruff、compileall、pip check、diff check 全部通过，skip 未计为 pass。
- [x] workflow actions 全部固定到审核后的 40 位 commit SHA，Ubuntu 为 24.04。
- [x] workflow 文本门禁强制 Slang 41/41 与 SystemVerilog equivalence 8/8，失败或 skip 均失败。
- [ ] 本轮普通 commit/push 后读取真实远端 run，四个 job 全部 success。

## 版本、wheel、SBOM 与 NOTICE

- [x] `pyproject.toml` 与 smoke script 使用 `0.2.0`；`pyslang==11.0.0` 保持精确固定。
- [x] README、release notes、checklist、MVP 边界和 `THIRD_PARTY_NOTICES` 使用正式 0.2.0
  发布冻结措辞，并继续声明不发布 EXE。
- [x] 构建 `hdl_x-0.2.0-py3-none-any.whl`：67 entries、2 个 entry points、3 个模板和 2 个 license files 完整；SHA-256 `834c447b3bc95bf256072f03c924a375c89ff3443aaebb80ad0c8a7ac1f1d5dc`。
- [x] clean wheelhouse smoke 在 `system_site_packages=False` venv 中仅用 `--no-index` 安装，
  doctor、真实 VHDL/SystemVerilog 转换及 golden 字节比较通过。
- [x] 从最终 wheelhouse 重建 CycloneDX 1.6 `SBOM.cdx.json`；包含 `hdl-x==0.2.0`、
  `pyGHDL==6.0.0`、`pyslang==11.0.0` 和 active `systemverilog` extra。
- [x] `THIRD_PARTY_NOTICES` 保持 pyGHDL/libghdl、pyslang/Slang 的许可证、上游源码和
  “不捆绑进 HDL-X wheel”边界；项目自有源码仍为 MIT、Copyright 2026 rh。
- [x] v0.2.0 不构建、不发布 PyInstaller EXE。
- [x] wheelhouse 官方 pyGHDL/pyslang wheel SHA-256 分别为 `624ce2fcb3163c16215e7d0390caaf91bd0ae50a77dcb2b60e2eae35a5ebe839`、`b9cae2cc3d856bf7e52620a74cf9e2bb687c280ecccf70fbb63e49e690e77a47`；VHDL/SV generated 与既有 golden 分别为 `aac65f543e01354dee26c04b817a5333a5a533695d337d814a95f2e7ac195428`、`137447ebe3e06115bccb2dd941977270b20ec400001b51bb7bcee778efabdb83`。
- [x] 最终 SBOM 共 21 个 project/dependency components，active extra 为 `systemverilog`，SHA-256 `d38f31295d0b87b8ebeb80233dcbfd967df3ad6b76a0bfde0c4ca1a3babd9f9d`。

## 发布授权

- [ ] 项目所有者明确说“允许发布”。
- [ ] 创建 annotated `v0.2.0` tag 并普通 push。
- [ ] 创建 GitHub Release 并附 wheel、源码归档、SBOM、THIRD_PARTY_NOTICES 和 SHA-256。

最终目标：Slang integration `41 passed, 0 skipped`；SystemVerilog compile/equivalence
`8 passed, 0 skipped`；VHDL semantic equivalence `2 passed, 0 skipped`；完整质量、isolated
wheelhouse smoke 和 VHDL golden 0 diff 全部通过。技术门禁完成仍只代表“可以请求发布授权”。
