from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    copy_metadata,
)


project_root = Path(SPECPATH).parents[1]
datas = [
    (
        str(project_root / "src" / "hdl_x" / "templates"),
        "hdl_x/templates",
    )
]
datas.extend(collect_data_files("pyGHDL"))
datas.extend(copy_metadata("pyGHDL"))
binaries = collect_dynamic_libs("pyGHDL")
hiddenimports = [
    "pyGHDL.dom",
    "pyGHDL.dom.Expression",
    "pyGHDL.dom.Literal",
    "pyGHDL.dom.Name",
    "pyGHDL.dom.NonStandard",
    "pyGHDL.dom.Symbol",
    "pyGHDL.dom._Translate",
    "pyGHDL.dom._Utils",
    "pyGHDL.libghdl",
    "pyGHDL.libghdl.errorout_memory",
    "pyGHDL.libghdl.flags",
    "pyGHDL.libghdl.libraries",
    "pyGHDL.libghdl.name_table",
    "pyGHDL.libghdl.utils",
    "pyGHDL.libghdl.vhdl.nodes",
    "pyGHDL.libghdl.vhdl.parse",
    "pyGHDL.libghdl.vhdl.sem",
]

analysis = Analysis(
    [str(project_root / "packaging" / "windows" / "hdl_x_gui.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "PIL",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "astroid",
        "cloudpickle",
        "debugpy",
        "dill",
        "docutils",
        "jedi",
        "jupyter_client",
        "matplotlib_inline",
        "mypy",
        "matplotlib",
        "numpy",
        "parso",
        "psutil",
        "pytest",
        "sphinx",
        "streamlit",
        "traitlets",
        "gi",
        "ipykernel",
        "ipywidgets",
        "zmq",
    ],
    noarchive=False,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="HDL-X",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

distribution = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HDL-X",
)
