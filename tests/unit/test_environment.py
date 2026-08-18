from hdl_x import environment
from hdl_x.parser.ghdl.runtime import PyGhdlRuntimeStatus


def test_environment_distinguishes_frontend_and_cli_validator() -> None:
    items = {item.name: item for item in environment.inspect_environment()}

    assert items["Python"].available
    assert items["Python"].required
    assert "GHDL frontend (pyGHDL/libghdl)" in items
    assert "GHDL CLI validator" in items
    assert items["GHDL frontend (pyGHDL/libghdl)"].required
    assert not items["GHDL CLI validator"].required


def test_environment_uses_the_same_exact_pyghdl_version_policy(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        environment,
        "inspect_pyghdl_runtime",
        lambda: PyGhdlRuntimeStatus(
            available=False,
            installed_version="6.0.1",
            code="HDLX-GHDL-VERSION",
            detail="不支持 pyGHDL 6.0.1；当前 backend 已验证版本为 6.0.0。",
            suggestion="安装 pyGHDL 6.0.0。",
        ),
    )

    items = {item.name: item for item in environment.inspect_environment()}
    frontend = items["GHDL frontend (pyGHDL/libghdl)"]

    assert not frontend.available
    assert frontend.version == "6.0.1"
    assert frontend.required
    assert "已验证版本为 6.0.0" in frontend.detail
