"""VHDL target 的名称、类型、表达式与条件 lowering。"""

from __future__ import annotations

import re

from hdl_x.diagnostics import GenerationError
from hdl_x.ir import (
    BinaryExpr,
    BinaryOperator,
    BooleanType,
    Concatenation,
    FunctionCall,
    Identifier,
    Index,
    IntegerType,
    Literal,
    LiteralKind,
    RangeDirection,
    RTLType,
    ScalarType,
    Slice,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    VectorRange,
    VectorType,
)
from hdl_x.transformer.identifier_resolver import NameStyle

_VHDL_KEYWORDS = frozenset(
    "abs access after alias all and architecture array assert assume attribute begin "
    "block body buffer bus case component configuration constant context cover default "
    "disconnect downto else elsif end entity exit fair file for force function generate "
    "generic group guarded if impure in inertial inout is label library linkage literal "
    "loop map mod nand new next nor not null of on open or others out package parameter "
    "port postponed procedure process property protected pure range record register reject "
    "release rem report restrict return rol ror select sequence severity shared signal sla "
    "sll sra srl strong subtype then to transport type unaffected units until use variable "
    "view vmode vprop vunit wait when while with xnor xor".split()
)

_BINARY_OPERATORS: dict[BinaryOperator, tuple[str, int]] = {
    BinaryOperator.LOGICAL_OR: ("or", 2),
    BinaryOperator.LOGICAL_AND: ("and", 3),
    BinaryOperator.BITWISE_OR: ("or", 4),
    BinaryOperator.BITWISE_XOR: ("xor", 5),
    BinaryOperator.BITWISE_XNOR: ("xnor", 5),
    BinaryOperator.BITWISE_AND: ("and", 6),
    BinaryOperator.EQUAL: ("=", 7),
    BinaryOperator.NOT_EQUAL: ("/=", 7),
    BinaryOperator.LESS_THAN: ("<", 8),
    BinaryOperator.LESS_EQUAL: ("<=", 8),
    BinaryOperator.GREATER_THAN: (">", 8),
    BinaryOperator.GREATER_EQUAL: (">=", 8),
    BinaryOperator.SHIFT_LEFT: ("sll", 9),
    BinaryOperator.SHIFT_RIGHT: ("srl", 9),
    BinaryOperator.ARITHMETIC_SHIFT_RIGHT: ("sra", 9),
    BinaryOperator.ADD: ("+", 10),
    BinaryOperator.SUBTRACT: ("-", 10),
    BinaryOperator.MULTIPLY: ("*", 11),
    BinaryOperator.DIVIDE: ("/", 11),
    BinaryOperator.MODULO: ("rem", 11),
    BinaryOperator.POWER: ("**", 12),
}

_UNARY_OPERATORS: dict[UnaryOperator, str] = {
    UnaryOperator.LOGICAL_NOT: "not ",
    UnaryOperator.BITWISE_NOT: "not ",
    UnaryOperator.NEGATE: "-",
    UnaryOperator.POSITIVE: "+",
    UnaryOperator.REDUCTION_AND: "and ",
    UnaryOperator.REDUCTION_OR: "or ",
    UnaryOperator.REDUCTION_XOR: "xor ",
}

_COMPARISONS = {
    BinaryOperator.EQUAL,
    BinaryOperator.NOT_EQUAL,
    BinaryOperator.LESS_THAN,
    BinaryOperator.LESS_EQUAL,
    BinaryOperator.GREATER_THAN,
    BinaryOperator.GREATER_EQUAL,
}


class VhdlNameAllocator:
    """按 VHDL basic identifier 和大小写不敏感规则稳定分配名称。"""

    def __init__(self, style: NameStyle) -> None:
        self._style = style
        self._used: set[str] = set()

    def reserve(self, name: str) -> None:
        self._used.add(name.casefold())

    def allocate(self, source: str) -> str:
        candidate = re.sub(r"[^A-Za-z0-9_]+", "_", self._apply_style(source))
        candidate = re.sub(r"_+", "_", candidate).strip("_")
        if not candidate or not candidate[0].isalpha():
            candidate = f"hdl_x_{candidate or 'name'}"
        if candidate.casefold() in _VHDL_KEYWORDS:
            candidate = f"{candidate}_hdl_x"
        base = candidate
        suffix = 2
        while candidate.casefold() in self._used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        self.reserve(candidate)
        return candidate

    def _apply_style(self, name: str) -> str:
        if self._style is NameStyle.PRESERVE:
            return name
        words = [
            part
            for part in re.split(r"[_\s]+|(?<=[a-z0-9])(?=[A-Z])", name)
            if part
        ]
        lowered = [word.lower() for word in words]
        if not lowered:
            return name
        if self._style is NameStyle.SNAKE_CASE:
            return "_".join(lowered)
        if self._style is NameStyle.CAMEL_CASE:
            return lowered[0] + "".join(word.capitalize() for word in lowered[1:])
        return "".join(word.capitalize() for word in lowered)


class VhdlExpressionLowering:
    """在一个 module scope 内完成 target expression/type 决策。"""

    def __init__(
        self,
        names: dict[str, str],
        rtl_types: dict[str, RTLType],
    ) -> None:
        self.names = names
        self.rtl_types = rtl_types

    def type_text(self, rtl_type: object) -> str:
        if isinstance(rtl_type, ScalarType):
            if rtl_type.signed:
                raise GenerationError(
                    "signed scalar 不能在不改变位宽语义时映射到 VHDL",
                    code="HDLX-V2V-SIGNED-SCALAR",
                    source_span=rtl_type.source_span,
                )
            return "std_logic"
        if isinstance(rtl_type, VectorType):
            base = "signed" if rtl_type.signed else "unsigned"
            return f"{base}({self.range_text(rtl_type.range)})"
        if isinstance(rtl_type, IntegerType):
            if rtl_type.minimum is not None and rtl_type.maximum is not None:
                return f"integer range {rtl_type.minimum} to {rtl_type.maximum}"
            return "integer"
        if isinstance(rtl_type, BooleanType):
            return "boolean"
        raise GenerationError(
            f"无法映射 RTL 类型 {type(rtl_type).__name__}",
            code="HDLX-V2V-TYPE",
            source_span=getattr(rtl_type, "source_span", None),
        )

    def range_text(self, value: VectorRange) -> str:
        direction = "to" if value.direction is RangeDirection.ASCENDING else "downto"
        return (
            f"{self.bound_text(value.left)} {direction} "
            f"{self.bound_text(value.right)}"
        )

    def bound_text(self, value: object) -> str:
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return self.expression(value)

    def expression(
        self,
        expression: object,
        *,
        replacements: dict[str, str] | None = None,
        parent: int = 0,
    ) -> str:
        replacements = replacements or {}
        if isinstance(expression, Identifier):
            return replacements.get(
                expression.name,
                self.names.get(expression.name, expression.name),
            )
        if isinstance(expression, Literal):
            return self._literal(expression)
        if isinstance(expression, UnaryExpr):
            precedence = 13
            operand = self.expression(
                expression.operand,
                replacements=replacements,
                parent=precedence,
            )
            text = _UNARY_OPERATORS[expression.operator] + operand
            return f"({text})" if precedence < parent else text
        if isinstance(expression, BinaryExpr):
            if expression.operator in {
                BinaryOperator.CASE_EQUAL,
                BinaryOperator.CASE_NOT_EQUAL,
            }:
                raise GenerationError(
                    "Verilog case equality 对 X/Z 的结果无法直接映射到 VHDL",
                    code="HDLX-V2V-CASE-EQUALITY",
                    source_span=expression.source_span,
                )
            operator, precedence = _BINARY_OPERATORS[expression.operator]
            left = self.expression(
                expression.left,
                replacements=replacements,
                parent=precedence,
            )
            right = self.expression(
                expression.right,
                replacements=replacements,
                parent=precedence + 1,
            )
            text = f"{left} {operator} {right}"
            return f"({text})" if precedence < parent else text
        if isinstance(expression, TernaryExpr):
            precedence = 1
            condition = self.condition(expression.condition, replacements=replacements)
            when_true = self.expression(
                expression.when_true,
                replacements=replacements,
                parent=precedence,
            )
            when_false = self.expression(
                expression.when_false,
                replacements=replacements,
                parent=precedence,
            )
            text = f"{when_true} when {condition} else {when_false}"
            return f"({text})" if precedence < parent else text
        if isinstance(expression, Concatenation):
            return " & ".join(
                self.expression(item, replacements=replacements, parent=7)
                for item in expression.parts
            )
        if isinstance(expression, Index):
            value = self.expression(expression.value, replacements=replacements, parent=14)
            index = self.expression(expression.index, replacements=replacements)
            return f"{value}({index})"
        if isinstance(expression, Slice):
            value = self.expression(expression.value, replacements=replacements, parent=14)
            direction = (
                "to" if expression.direction is RangeDirection.ASCENDING else "downto"
            )
            left = self.expression(expression.left, replacements=replacements)
            right = self.expression(expression.right, replacements=replacements)
            return f"{value}({left} {direction} {right})"
        if isinstance(expression, FunctionCall):
            raise GenerationError(
                "function call 不在 v0.3 MVP 内",
                code="HDLX-V2V-FUNCTION",
                source_span=expression.source_span,
            )
        raise GenerationError(
            f"无法渲染表达式 {type(expression).__name__}",
            code="HDLX-V2V-EXPRESSION",
            source_span=getattr(expression, "source_span", None),
        )

    def condition(
        self,
        expression: object,
        *,
        replacements: dict[str, str] | None = None,
    ) -> str:
        replacements = replacements or {}
        if isinstance(expression, UnaryExpr) and expression.operator is UnaryOperator.LOGICAL_NOT:
            if self._is_bit_expression(expression.operand):
                return f"{self.expression(expression.operand, replacements=replacements)} = '0'"
            nested = self.condition(expression.operand, replacements=replacements)
            return f"not ({nested})"
        if isinstance(expression, BinaryExpr):
            if expression.operator is BinaryOperator.LOGICAL_AND:
                left = self.condition(expression.left, replacements=replacements)
                right = self.condition(expression.right, replacements=replacements)
                return f"({left}) and ({right})"
            if expression.operator is BinaryOperator.LOGICAL_OR:
                left = self.condition(expression.left, replacements=replacements)
                right = self.condition(expression.right, replacements=replacements)
                return f"({left}) or ({right})"
            if expression.operator in _COMPARISONS:
                return self.expression(expression, replacements=replacements)
        if self._is_bit_expression(expression):
            value = self.expression(expression, replacements=replacements)
            return f"{value} = '1'"
        if isinstance(self.target_type(expression), IntegerType):
            value = self.expression(expression, replacements=replacements)
            return f"{value} /= 0"
        raise GenerationError(
            "Verilog integral condition 缺少可证明的一位/boolean 类型",
            code="HDLX-V2V-CONDITION-TYPE",
            source_span=getattr(expression, "source_span", None),
        )

    def assignment_value(
        self,
        value: object,
        target: object,
        *,
        target_text: str,
        replacements: dict[str, str] | None = None,
    ) -> str:
        rtl_type = self.target_type(target)
        if isinstance(value, Literal) and type(value.value) is int:
            integer = value.value
            if isinstance(rtl_type, ScalarType):
                if integer not in {0, 1}:
                    raise GenerationError(
                        "unsized integer 无法无损赋给单比特 target",
                        code="HDLX-V2V-UNSIZED-LITERAL",
                        source_span=value.source_span,
                    )
                return f"'{integer}'"
            if isinstance(rtl_type, VectorType):
                function = "to_signed" if rtl_type.signed else "to_unsigned"
                return f"{function}({integer}, {target_text}'length)"
        return self.expression(value, replacements=replacements)

    def target_type(self, target: object) -> RTLType | None:
        name = self.root_name(target)
        return None if name is None else self.rtl_types.get(name)

    def _is_bit_expression(self, expression: object) -> bool:
        rtl_type = self.target_type(expression)
        if isinstance(rtl_type, ScalarType | BooleanType):
            return True
        if isinstance(expression, Literal):
            return expression.literal_kind is LiteralKind.BIT or expression.bit_width == 1
        if isinstance(expression, Index):
            return True
        return False

    @classmethod
    def root_name(cls, target: object) -> str | None:
        if isinstance(target, Identifier):
            return target.name
        if isinstance(target, Index | Slice):
            return cls.root_name(target.value)
        return None

    @staticmethod
    def _literal(literal: Literal) -> str:
        value = literal.value
        if type(value) is bool:
            return "true" if value else "false"
        if type(value) is int:
            return str(value)
        unquoted = (
            value[1:-1]
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\""
            else value
        )
        bits = unquoted.replace("_", "").upper()
        if literal.literal_kind is LiteralKind.BIT or len(bits) == 1:
            return f"'{bits}'"
        if (
            literal.literal_kind in {LiteralKind.BIT_VECTOR, LiteralKind.UNSPECIFIED}
            and re.fullmatch(r"[01XZ]+", bits)
        ):
            return f'"{bits}"'
        raise GenerationError(
            f"literal {value!r} 无法安全映射到 VHDL",
            code="HDLX-V2V-LITERAL",
            source_span=literal.source_span,
        )


__all__ = ["VhdlExpressionLowering", "VhdlNameAllocator"]
