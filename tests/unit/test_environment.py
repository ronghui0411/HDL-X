from hdl_x.environment import inspect_environment


def test_environment_distinguishes_frontend_and_cli_validator() -> None:
    items = {item.name: item for item in inspect_environment()}

    assert items["Python"].available
    assert items["Python"].required
    assert "GHDL frontend (pyGHDL/libghdl)" in items
    assert "GHDL CLI validator" in items
    assert items["GHDL frontend (pyGHDL/libghdl)"].required
    assert not items["GHDL CLI validator"].required
