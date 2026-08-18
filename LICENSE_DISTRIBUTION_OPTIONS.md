# HDL-X v0.1 许可证与分发技术准备

本文档不是法律意见。它记录三种分发边界，以及项目所有者对 v0.1.1 的明确技术决定。

## v0.1.1 所有者决定

- 版权主体：`rh`；版权年份：`2026`。
- HDL-X 自有源码采用 SPDX `MIT`，最终文本见根目录 `LICENSE`。
- 发布源码和纯 Python wheel；暂缓 PyInstaller EXE，不上传现有 `dist/HDL-X`。
- 第三方清单文件名为 `THIRD_PARTY_NOTICES`，同时保留在仓库根目录和 GitHub Release。
- HDL-X 对应源码由公开 GitHub 仓库与 v0.1.1 Release source archive 提供并保留。
- 发布 CycloneDX SBOM；不要求 wheel/源码签名；Windows EXE 代码签名随 EXE 一并暂缓。
- 项目所有者明确不要求本次发布进行外部法律审查。

以上是所有者给出的发布决定，不是对 MIT 与 GPL-2.0-or-later 相互作用的法律结论。

## 当前依赖边界

- HDL-X 源码直接导入 pyGHDL/libghdl，支持的运行时版本精确为 `6.0.0`。
- HDL-X Python wheel 不包含 pyGHDL、libghdl DLL/SO 或 GHDL VHDL 库；metadata 只声明
  `Requires-Dist: pyGHDL==6.0.0`。
- PyInstaller EXE 会收集 pyGHDL metadata、动态库和标准/IEEE VHDL 库，因此与纯
  Python wheel 是不同的二进制分发边界。
- 官方 pyGHDL/libghdl 标示为 GPL-2.0-or-later。项目所有者需要确认该许可证对每种
  分发方式的具体影响；本文档不作兼容性或衍生作品判断。

## 方案一：源码发布

建议准备但尚未最终确定的材料：

- 项目所有者选定的顶层 `LICENSE` 和版权声明；
- `NOTICE` 或 `THIRD_PARTY_NOTICES`，列出 pyGHDL/libghdl 与其他直接依赖、版本、主页、
  SPDX 标识和许可证文本位置；
- 可复现的源码归档，包含构建脚本、测试 fixtures/goldens、release checklist 和依赖锁定
  信息；
- 官方 pyGHDL 6.0.0 release、源码仓库、wheel SHA-256 和用户独立安装说明；
- 明确声明源码归档不包含 pyGHDL 二进制，除非所有者另行批准并补齐相应材料。

技术影响：制品最透明，用户需要自行准备 Python、pyGHDL 和可选验证工具；不能提供
开箱即用的独立 GUI 体验。

## 方案二：纯 Python wheel

建议在源码发布材料基础上再准备：

- wheel metadata 中的最终 license expression/file 和项目 URL；
- 随 wheel 或同一 release 提供的 `NOTICE`/第三方许可证清单；
- 明确的 ABI/平台安装矩阵、官方 pyGHDL wheel 下载位置和校验值；
- 证明 wheel archive 不含 `pyGHDL`、`libghdl` 或 GHDL VHDL 库的文件清单；
- 完整 wheelhouse manifest 与 SHA-256，用于隔离安装复现，但不得把第三方 wheel 误称为
  HDL-X 自有制品；
- HDL-X 源码获取地址，以及项目所有者/法律顾问认为适用的第三方源码获取信息。

技术影响：HDL-X wheel 可保持 `py3-none-any`，但 pyGHDL 本身是 ABI/平台相关 wheel，
普通 PyPI 单步安装当前不可用；用户或 CI 必须先取得官方 asset，或者使用完整 wheelhouse。

## 方案三：PyInstaller EXE

建议在前两种方案材料基础上再准备：

- 分发目录内可直接访问的项目 LICENSE、pyGHDL/GHDL 许可证文本和所有第三方许可证；
- 完整 `NOTICE`、组件版本/SHA-256、SBOM 或等价的机器可读依赖清单；
- 与实际 EXE 精确对应的 HDL-X 源码、PyInstaller spec、构建脚本和可复现构建说明；
- 对内置 pyGHDL/libghdl、GHDL 标准/IEEE 库及其他二进制组件，准备项目所有者或法律
  顾问认定所需的对应源码、源码下载归档或其他有效源码获取材料；
- 明确区分 HDL-X 自有代码、第三方代码、系统运行库和仅聚合的数据文件；
- 发布前重新审查代码签名、完整目录分发和升级/安全修复流程。

技术影响：用户无需另装 Python/GHDL，但制品最大、平台专用，第三方材料和长期源码
可获得性要求也最复杂。在所有者确认前，不应公开发布当前 `dist/HDL-X` 或其 ZIP。

## v0.1.1 未采用的分发边界

PyInstaller EXE 不属于 v0.1.1 Release。若未来启用，必须重新确认内置 pyGHDL/libghdl、
第三方许可证全文、对应源码材料、SBOM、完整目录发布以及 Windows 代码签名策略；本次
MIT 选择和纯 wheel 审查不得自动视为对 EXE 分发的批准。
