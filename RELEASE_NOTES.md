# HDL-X v0.1.1

HDL-X v0.1.1 提供离线的 VHDL-2008 synthesizable subset → Verilog-2001 转换，重点保留
RTL 语义、层次、generics/parameters、generate 结构、时钟/复位过程和源码注释。

## 制品

- `hdl_x-0.1.1-py3-none-any.whl`：纯 Python HDL-X wheel；不捆绑 pyGHDL/libghdl。
- `HDL-X-0.1.1-source.zip`：与 `v0.1.1` tag 对应的完整源码归档。
- `SBOM.cdx.json`：CycloneDX 1.6 运行时 wheelhouse SBOM。
- `THIRD_PARTY_NOTICES`：第三方依赖、许可证和对应源码位置。
- `SHA256SUMS.txt`：Release 附件校验值。

v0.1.1 不提供 PyInstaller EXE。仓库中已有的本地 EXE 构建结果不属于本次 Release。

## 安装

要求 Python 3.10+，并精确使用官方 pyGHDL/libghdl 6.0.0。pyGHDL wheel 由
[GHDL 6.0.0 Release](https://github.com/ghdl/ghdl/releases/tag/v6.0.0) 按 Python ABI
和平台分别提供，不包含在 HDL-X wheel 中。以 CPython 3.13 Windows x64 为例：

```powershell
python -m pip install .\pyghdl-6.0.0-cp313-cp313-win_amd64.whl
python -m pip install .\hdl_x-0.1.1-py3-none-any.whl
hdl-x doctor
```

转换示例：

```powershell
hdl-x convert input.vhd --from vhdl --to verilog -o output.v --strict
```

支持子集、拒绝边界、初始状态与完整 IEEE 9-state 限制见 README。

## 许可证

HDL-X 自有源码：MIT，`Copyright (c) 2026 rh`。pyGHDL/libghdl 及其他依赖遵循各自
许可证；详见 `THIRD_PARTY_NOTICES` 与 `SBOM.cdx.json`。这些材料不构成法律意见。
