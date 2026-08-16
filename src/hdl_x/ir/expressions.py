"""语言无关的 canonical RTL 表达式。"""

from __future__ import annotations

from enum import Enum
from typing import Annotated
from typing import Literal as TypingLiteral

from pydantic import Field, field_validator, model_validator

from .base import IRNode, RangeDirection


class UnaryOperator(str, Enum):
    """一元运算的 canonical 语义。"""

    LOGICAL_NOT = "logical_not"
    BITWISE_NOT = "bitwise_not"
    NEGATE = "negate"
    POSITIVE = "positive"
    REDUCTION_AND = "reduction_and"
    REDUCTION_OR = "reduction_or"
    REDUCTION_XOR = "reduction_xor"


class BinaryOperator(str, Enum):
    """二元运算的 canonical 语义。"""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    MODULO = "modulo"
    POWER = "power"
    LOGICAL_AND = "logical_and"
    LOGICAL_OR = "logical_or"
    BITWISE_AND = "bitwise_and"
    BITWISE_OR = "bitwise_or"
    BITWISE_XOR = "bitwise_xor"
    BITWISE_XNOR = "bitwise_xnor"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    CASE_EQUAL = "case_equal"
    CASE_NOT_EQUAL = "case_not_equal"
    LESS_THAN = "less_than"
    LESS_EQUAL = "less_equal"
    GREATER_THAN = "greater_than"
    GREATER_EQUAL = "greater_equal"
    SHIFT_LEFT = "shift_left"
    SHIFT_RIGHT = "shift_right"
    ARITHMETIC_SHIFT_RIGHT = "arithmetic_shift_right"


class LiteralKind(str, Enum):
    """字面量携带的逻辑类别。"""

    UNSPECIFIED = "unspecified"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    BIT = "bit"
    BIT_VECTOR = "bit_vector"
    STRING = "string"


class Expression(IRNode):
    """所有 canonical 表达式的共同基类。"""


class Identifier(Expression):
    """已经解析或等待 identifier resolver 解析的名称。"""

    kind: TypingLiteral["identifier"] = "identifier"
    name: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier name must not be blank")
        return value


class Literal(Expression):
    """不绑定源语言拼写的字面量值。"""

    kind: TypingLiteral["literal"] = "literal"
    value: bool | int | str
    literal_kind: LiteralKind = LiteralKind.UNSPECIFIED
    bit_width: int | None = Field(default=None, ge=1)
    signed: bool = False

    @model_validator(mode="after")
    def validate_literal_semantics(self) -> Literal:
        """拒绝类别、Python 值与显式位宽互相矛盾的字面量。"""

        value = self.value
        kind = self.literal_kind

        if type(value) is bool and self.bit_width not in (None, 1):
            raise ValueError("boolean value width must be one")

        if kind is LiteralKind.INTEGER and type(value) is not int:
            raise ValueError("integer literal requires an integer value")
        if kind is LiteralKind.BOOLEAN and type(value) is not bool:
            raise ValueError("boolean literal requires a boolean value")
        if kind is LiteralKind.STRING:
            if not isinstance(value, str):
                raise ValueError("string literal requires a string value")
            if self.bit_width is not None:
                raise ValueError("string literal cannot declare a bit width")

        if kind is LiteralKind.BIT:
            bits = self._validated_bits(value, expected_kind="bit")
            if len(bits) != 1:
                raise ValueError("bit literal must contain exactly one bit")
            if self.bit_width not in (None, 1):
                raise ValueError("bit literal width must be one")

        if kind is LiteralKind.BIT_VECTOR:
            bits = self._validated_bits(value, expected_kind="bit-vector")
            if self.bit_width is not None and self.bit_width != len(bits):
                raise ValueError("bit-vector width does not match its value")

        if kind is LiteralKind.UNSPECIFIED and isinstance(value, str):
            if self.bit_width is not None:
                bits = self._validated_bits(value, expected_kind="sized")
                if self.bit_width != len(bits):
                    raise ValueError("literal width does not match its bit value")
        return self

    @staticmethod
    def _validated_bits(value: bool | int | str, *, expected_kind: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{expected_kind} literal requires a string value")
        unquoted = value
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            unquoted = value[1:-1]
        bits = unquoted.replace("_", "")
        if not bits or any(character not in "01xXzZ" for character in bits):
            raise ValueError(f"{expected_kind} literal contains unsupported bit values")
        return bits


class UnaryExpr(Expression):
    """一元表达式。"""

    kind: TypingLiteral["unary"] = "unary"
    operator: UnaryOperator
    operand: ExpressionNode


class BinaryExpr(Expression):
    """二元表达式。"""

    kind: TypingLiteral["binary"] = "binary"
    left: ExpressionNode
    operator: BinaryOperator
    right: ExpressionNode


class TernaryExpr(Expression):
    """条件选择表达式。"""

    kind: TypingLiteral["ternary"] = "ternary"
    condition: ExpressionNode
    when_true: ExpressionNode
    when_false: ExpressionNode


class Concatenation(Expression):
    """按顺序连接多个表达式。"""

    kind: TypingLiteral["concatenation"] = "concatenation"
    parts: list[ExpressionNode] = Field(min_length=1)


class Index(Expression):
    """单个元素索引。"""

    kind: TypingLiteral["index"] = "index"
    value: ExpressionNode
    index: ExpressionNode


class Slice(Expression):
    """保留索引方向的区间选择。"""

    kind: TypingLiteral["slice"] = "slice"
    value: ExpressionNode
    left: ExpressionNode
    right: ExpressionNode
    direction: RangeDirection


class FunctionCall(Expression):
    """语义 lowering 前后均可引用的函数调用。"""

    kind: TypingLiteral["function_call"] = "function_call"
    function: Identifier
    arguments: list[ExpressionNode] = Field(default_factory=list)

    @field_validator("function", mode="before")
    @classmethod
    def convert_function_name(cls, value: object) -> object:
        if isinstance(value, str):
            return {"kind": "identifier", "name": value}
        return value


ExpressionNode = Annotated[
    Identifier
    | Literal
    | UnaryExpr
    | BinaryExpr
    | TernaryExpr
    | Concatenation
    | Index
    | Slice
    | FunctionCall,
    Field(discriminator="kind"),
]


for _model in (
    UnaryExpr,
    BinaryExpr,
    TernaryExpr,
    Concatenation,
    Index,
    Slice,
    FunctionCall,
):
    _model.model_rebuild(_types_namespace={"ExpressionNode": ExpressionNode})
