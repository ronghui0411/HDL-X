"""canonical four-state comparison 的稳定 Verilog-2001 lowering。"""

from hdl_x.generator.verilog import VerilogGenerator
from hdl_x.ir import (
    BinaryExpr,
    BinaryOperator,
    ContinuousAssignment,
    Design,
    Identifier,
    Literal,
    LiteralKind,
    Module,
    Port,
    PortDirection,
    ScalarType,
)


def test_case_equality_operator_renders_exactly() -> None:
    module = Module(
        name="case_equal",
        ports=[
            Port(name="a", direction=PortDirection.INPUT, rtl_type=ScalarType()),
            Port(name="y", direction=PortDirection.OUTPUT, rtl_type=ScalarType()),
        ],
        items=[
            ContinuousAssignment(
                target=Identifier(name="y"),
                value=BinaryExpr(
                    left=Identifier(name="a"),
                    operator=BinaryOperator.CASE_EQUAL,
                    right=Literal(
                        value="X",
                        literal_kind=LiteralKind.BIT,
                        bit_width=1,
                    ),
                ),
            )
        ],
    )

    text = VerilogGenerator().generate(Design(modules=[module]))

    assert "assign y = a === 1'bx;" in text
