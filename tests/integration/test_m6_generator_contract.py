"""Milestone 6 canonical hierarchy、instance 与 generator 合约回归。"""

import pytest

from hdl_x.diagnostics import SemanticError
from hdl_x.generator import VerilogGenerator
from hdl_x.ir import (
    BinaryExpr,
    BinaryOperator,
    ContinuousAssignment,
    Design,
    Identifier,
    Instance,
    IntegerType,
    Literal,
    Module,
    Parameter,
    ParameterBinding,
    Port,
    PortBinding,
    PortDirection,
    RangeDirection,
    ScalarType,
    Signal,
    VectorRange,
    VectorType,
)


def _scalar_port(name: str, direction: PortDirection) -> Port:
    return Port(name=name, direction=direction, rtl_type=ScalarType())


def _pass_cell(name: str = "PassCell") -> Module:
    return Module(
        name=name,
        ports=[
            _scalar_port("data_in", PortDirection.INPUT),
            _scalar_port("data_out", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="data_out"),
                value=Identifier(name="data_in"),
            )
        ],
    )


def _generate(*modules: Module, top: str | None = None) -> str:
    return VerilogGenerator().generate(Design(modules=list(modules), top=top))


def test_m6_simple_named_instance_preserves_module_and_instance_hierarchy() -> None:
    top = Module(
        name="Top",
        ports=[
            _scalar_port("source", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        items=[
            Instance(
                referenced_unit="PassCell",
                name="u_pass",
                port_bindings=[
                    PortBinding(formal="data_in", value=Identifier(name="source")),
                    PortBinding(formal="data_out", value=Identifier(name="result")),
                ],
            )
        ],
    )

    output = _generate(_pass_cell(), top, top="Top")

    assert output == """module PassCell (
    input wire data_in,
    output wire data_out
);

assign data_out = data_in;

endmodule

module Top (
    input wire source,
    output wire result
);

PassCell u_pass (
    .data_in(source),
    .data_out(result)
);

endmodule
"""


def test_m6_two_instances_keep_names_and_intermediate_signal() -> None:
    top = Module(
        name="TwoStage",
        ports=[
            _scalar_port("source", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        signals=[Signal(name="between_stages", rtl_type=ScalarType())],
        items=[
            Instance(
                referenced_unit="PassCell",
                name="u_first",
                port_bindings=[
                    PortBinding(position=0, value=Identifier(name="source")),
                    PortBinding(position=1, value=Identifier(name="between_stages")),
                ],
            ),
            Instance(
                referenced_unit="PassCell",
                name="u_second",
                port_bindings=[
                    PortBinding(position=0, value=Identifier(name="between_stages")),
                    PortBinding(position=1, value=Identifier(name="result")),
                ],
            ),
        ],
    )

    output = _generate(_pass_cell(), top, top="TwoStage")

    assert "wire between_stages;" in output
    assert "PassCell u_first (\n    source,\n    between_stages\n);" in output
    assert "PassCell u_second (\n    between_stages,\n    result\n);" in output
    assert output.count("PassCell u_") == 2


def test_m6_named_bindings_follow_vhdl_case_insensitive_formals() -> None:
    child = Module(
        name="NamedChild",
        ports=[
            _scalar_port("DataIn", PortDirection.INPUT),
            _scalar_port("DataOut", PortDirection.OUTPUT),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="DATAOUT"),
                value=Identifier(name="datain"),
            )
        ],
    )
    top = Module(
        name="NamedTop",
        ports=[
            _scalar_port("source", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        items=[
            Instance(
                referenced_unit="namedchild",
                name="u_named",
                port_bindings=[
                    PortBinding(formal="datain", value=Identifier(name="SOURCE")),
                    PortBinding(formal="DATAOUT", value=Identifier(name="RESULT")),
                ],
            )
        ],
    )

    output = _generate(child, top, top="NamedTop")

    assert "NamedChild u_named (" in output
    assert ".DataIn(source)," in output
    assert ".DataOut(result)" in output


def test_m6_parameterized_instance_preserves_symbolic_width_and_override() -> None:
    width_minus_one = BinaryExpr(
        left=Identifier(name="WIDTH"),
        operator=BinaryOperator.SUBTRACT,
        right=Literal(value=1),
    )
    child = Module(
        name="VectorChild",
        parameters=[
            Parameter(name="WIDTH", rtl_type=IntegerType(), default=Literal(value=8))
        ],
        ports=[
            Port(
                name="data_in",
                direction=PortDirection.INPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=width_minus_one,
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
            Port(
                name="data_out",
                direction=PortDirection.OUTPUT,
                rtl_type=VectorType(
                    range=VectorRange(
                        left=width_minus_one.model_copy(deep=True),
                        right=0,
                        direction=RangeDirection.DESCENDING,
                    )
                ),
            ),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="data_out"),
                value=Identifier(name="data_in"),
            )
        ],
    )
    top_width_minus_one = BinaryExpr(
        left=Identifier(name="TOP_WIDTH"),
        operator=BinaryOperator.SUBTRACT,
        right=Literal(value=1),
    )
    top_type = VectorType(
        range=VectorRange(
            left=top_width_minus_one,
            right=0,
            direction=RangeDirection.DESCENDING,
        )
    )
    top = Module(
        name="ParameterizedTop",
        parameters=[
            Parameter(
                name="TOP_WIDTH", rtl_type=IntegerType(), default=Literal(value=16)
            )
        ],
        ports=[
            Port(
                name="source",
                direction=PortDirection.INPUT,
                rtl_type=top_type,
            ),
            Port(
                name="result",
                direction=PortDirection.OUTPUT,
                rtl_type=top_type.model_copy(deep=True),
            ),
        ],
        items=[
            Instance(
                referenced_unit="VectorChild",
                name="u_vector",
                parameter_bindings=[
                    ParameterBinding(
                        formal="WIDTH", value=Identifier(name="TOP_WIDTH")
                    )
                ],
                port_bindings=[
                    PortBinding(formal="data_in", value=Identifier(name="source")),
                    PortBinding(formal="data_out", value=Identifier(name="result")),
                ],
            )
        ],
    )

    output = _generate(child, top, top="ParameterizedTop")

    assert "parameter integer WIDTH = 8" in output
    assert "input wire [WIDTH - 1:0] data_in" in output
    assert "parameter integer TOP_WIDTH = 16" in output
    assert "input wire [TOP_WIDTH - 1:0] source" in output
    assert "VectorChild #(\n    .WIDTH(TOP_WIDTH)\n) u_vector (" in output


def test_m6_positional_parameter_override_and_open_ports_render_explicitly() -> None:
    child = Module(
        name="OpenChild",
        parameters=[
            Parameter(name="WIDTH", rtl_type=IntegerType(), default=Literal(value=1))
        ],
        ports=[
            _scalar_port("data_in", PortDirection.INPUT),
            _scalar_port("unused", PortDirection.INPUT),
            _scalar_port("data_out", PortDirection.OUTPUT),
        ],
    )
    top = Module(
        name="OpenTop",
        ports=[_scalar_port("source", PortDirection.INPUT)],
        items=[
            Instance(
                referenced_unit="OpenChild",
                name="u_named_open",
                parameter_bindings=[
                    ParameterBinding(formal="WIDTH", value=Literal(value=2))
                ],
                port_bindings=[
                    PortBinding(formal="data_in", value=Identifier(name="source")),
                    PortBinding(formal="unused", value=None),
                    PortBinding(formal="data_out", value=None),
                ],
            ),
            Instance(
                referenced_unit="OpenChild",
                name="u_positional_open",
                parameter_bindings=[ParameterBinding(position=0, value=Literal(value=4))],
                port_bindings=[
                    PortBinding(position=0, value=Identifier(name="source")),
                    PortBinding(position=1, value=None),
                    PortBinding(position=2, value=None),
                ],
            ),
        ],
    )

    output = _generate(child, top, top="OpenTop")

    assert ".WIDTH(2)" in output
    assert ".unused()" in output
    assert ".data_out()" in output
    assert "OpenChild #(\n    4\n) u_positional_open (" in output
    assert "    /* open */,\n    /* open */" in output
    assert """OpenChild #(
    4
) u_positional_open (
    source,
    /* open */,
    /* open */
);""" in output


@pytest.mark.parametrize(
    ("binding", "expected_code"),
    [
        (PortBinding(formal="missing", value=Identifier(name="source")),
         "HDLX-INSTANCE-UNKNOWN-PORT"),
        (ParameterBinding(formal="MISSING", value=Literal(value=2)),
         "HDLX-INSTANCE-UNKNOWN-PARAMETER"),
        (PortBinding(position=2, value=Identifier(name="source")),
         "HDLX-INSTANCE-PORT-RANGE"),
        (ParameterBinding(position=1, value=Literal(value=2)),
         "HDLX-INSTANCE-PARAMETER-RANGE"),
    ],
    ids=["unknown-port", "unknown-parameter", "port-out-of-range", "parameter-out-of-range"],
)
def test_m6_known_unit_rejects_invalid_formals_and_positions(
    binding: PortBinding | ParameterBinding,
    expected_code: str,
) -> None:
    child = Module(
        name="CheckedChild",
        parameters=[
            Parameter(name="WIDTH", rtl_type=IntegerType(), default=Literal(value=1))
        ],
        ports=[_scalar_port("data_in", PortDirection.INPUT)],
    )
    instance_arguments: dict[str, object]
    if isinstance(binding, PortBinding):
        instance_arguments = {"port_bindings": [binding]}
    else:
        instance_arguments = {"parameter_bindings": [binding]}
    top = Module(
        name="CheckedTop",
        ports=[_scalar_port("source", PortDirection.INPUT)],
        items=[
            Instance(
                referenced_unit="CheckedChild",
                name="u_bad",
                **instance_arguments,
            )
        ],
    )

    with pytest.raises(SemanticError) as raised:
        _generate(child, top, top="CheckedTop")

    assert raised.value.code == expected_code


def test_m6_reserved_words_and_sanitization_collisions_are_deterministic() -> None:
    child = Module(
        name="module",
        parameters=[
            Parameter(name="parameter", rtl_type=IntegerType(), default=Literal(value=1))
        ],
        ports=[
            _scalar_port("input", PortDirection.INPUT),
            _scalar_port("output", PortDirection.OUTPUT),
        ],
        signals=[
            Signal(name="a-b", rtl_type=ScalarType()),
            Signal(name="a_b", rtl_type=ScalarType()),
            Signal(name="wire", rtl_type=ScalarType()),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="output"),
                value=Identifier(name="input"),
            )
        ],
    )
    top = Module(
        name="top",
        ports=[
            _scalar_port("source", PortDirection.INPUT),
            _scalar_port("result", PortDirection.OUTPUT),
        ],
        items=[
            Instance(
                referenced_unit="module",
                name="instance",
                parameter_bindings=[
                    ParameterBinding(formal="parameter", value=Literal(value=2))
                ],
                port_bindings=[
                    PortBinding(formal="input", value=Identifier(name="source")),
                    PortBinding(formal="output", value=Identifier(name="result")),
                ],
            )
        ],
    )
    generator = VerilogGenerator()

    output = generator.generate(Design(modules=[child, top], top="top"))

    assert "module module_hdl_x #(\n    parameter integer parameter_hdl_x = 1" in output
    assert "input wire input_hdl_x" in output
    assert "output wire output_hdl_x" in output
    assert "wire a_b;" in output
    assert "wire a_b_2;" in output
    assert "wire wire_hdl_x;" in output
    assert "module_hdl_x #(\n    .parameter_hdl_x(2)\n) instance_hdl_x (" in output
    assert ".input_hdl_x(source)" in output
    assert ".output_hdl_x(result)" in output
    assert generator.name_mappings["module::module"] == "module_hdl_x"
    assert generator.name_mappings["module::object::a-b"] == "a_b"
    assert generator.name_mappings["module::object::a_b"] == "a_b_2"


@pytest.mark.parametrize(
    "modules",
    [
        [
            Module(
                name="CasePorts",
                ports=[
                    _scalar_port("Data", PortDirection.INPUT),
                    _scalar_port("data", PortDirection.OUTPUT),
                ],
            )
        ],
        [Module(name="Child"), Module(name="child")],
    ],
    ids=["declaration", "module"],
)
def test_m6_vhdl_case_insensitive_collisions_fail_explicitly(
    modules: list[Module],
) -> None:
    with pytest.raises(SemanticError) as raised:
        VerilogGenerator().generate(Design(modules=modules))

    assert raised.value.code == "HDLX-NAME-DUPLICATE"
