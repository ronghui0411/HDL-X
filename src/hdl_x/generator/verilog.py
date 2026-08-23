"""从 canonical RTL IR 生成可读的 Verilog-2001。"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from hdl_x.diagnostics import GenerationError
from hdl_x.ir import (
    ActiveLevel,
    BinaryExpr,
    BinaryOperator,
    BlockStatement,
    BooleanType,
    CaseStatement,
    CombinationalProcess,
    Comment,
    CommentKind,
    Concatenation,
    ContinuousAssignment,
    Design,
    EdgeKind,
    ForGenerate,
    ForStatement,
    FunctionCall,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Instance,
    IntegerType,
    IRNode,
    Literal,
    LiteralKind,
    Module,
    NullStatement,
    Parameter,
    ParameterBinding,
    Port,
    PortBinding,
    ProceduralAssignment,
    RangeDirection,
    ResetKind,
    ScalarType,
    SequentialProcess,
    Signal,
    Slice,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    Variable,
    VectorRange,
    VectorType,
)
from hdl_x.transformer.identifier_resolver import NameStyle
from hdl_x.transformer.type_lowering import DriverAnalysis

from .base import Generator
from .verilog_ir import (
    VerilogAssignmentOperator,
    VerilogRenderIR,
    VerilogStorageKind,
)
from .verilog_lowering import VerilogLowering

_UNARY_OPERATORS: dict[UnaryOperator, str] = {
    UnaryOperator.LOGICAL_NOT: "!",
    UnaryOperator.BITWISE_NOT: "~",
    UnaryOperator.NEGATE: "-",
    UnaryOperator.POSITIVE: "+",
    UnaryOperator.REDUCTION_AND: "&",
    UnaryOperator.REDUCTION_OR: "|",
    UnaryOperator.REDUCTION_XOR: "^",
}

_BINARY_OPERATORS: dict[BinaryOperator, tuple[str, int]] = {
    BinaryOperator.LOGICAL_OR: ("||", 2),
    BinaryOperator.LOGICAL_AND: ("&&", 3),
    BinaryOperator.BITWISE_OR: ("|", 4),
    BinaryOperator.BITWISE_XOR: ("^", 5),
    BinaryOperator.BITWISE_XNOR: ("^~", 5),
    BinaryOperator.BITWISE_AND: ("&", 6),
    BinaryOperator.EQUAL: ("==", 7),
    BinaryOperator.NOT_EQUAL: ("!=", 7),
    BinaryOperator.CASE_EQUAL: ("===", 7),
    BinaryOperator.CASE_NOT_EQUAL: ("!==", 7),
    BinaryOperator.LESS_THAN: ("<", 8),
    BinaryOperator.LESS_EQUAL: ("<=", 8),
    BinaryOperator.GREATER_THAN: (">", 8),
    BinaryOperator.GREATER_EQUAL: (">=", 8),
    BinaryOperator.SHIFT_LEFT: ("<<", 9),
    BinaryOperator.SHIFT_RIGHT: (">>", 9),
    BinaryOperator.ARITHMETIC_SHIFT_RIGHT: (">>>", 9),
    BinaryOperator.ADD: ("+", 10),
    BinaryOperator.SUBTRACT: ("-", 10),
    BinaryOperator.MULTIPLY: ("*", 11),
    BinaryOperator.DIVIDE: ("/", 11),
    BinaryOperator.MODULO: ("%", 11),
    BinaryOperator.POWER: ("**", 12),
}


class VerilogRenderer:
    """只渲染已经完成 Verilog-specific lowering 的目标 IR。"""

    def __init__(
        self,
        *,
        template_directory: Path | None = None,
        indent: str = "    ",
    ) -> None:
        directory = template_directory or (
            Path(__file__).resolve().parent.parent / "templates" / "verilog"
        )
        self._environment = Environment(
            loader=FileSystemLoader(str(directory)),
            autoescape=False,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        self._module_template = self._environment.get_template("module.j2")
        self._item_template = self._environment.get_template("item.j2")
        self._statement_template = self._environment.get_template("statement.j2")
        self._indent = indent
        self._storage_kinds: Mapping[int, VerilogStorageKind] = {}
        self._assignment_operators: Mapping[int, VerilogAssignmentOperator] = {}

    def render(self, render_ir: VerilogRenderIR) -> str:
        """渲染目标 IR，并保证返回文本以一个换行结束。"""

        if not isinstance(render_ir, VerilogRenderIR):
            raise TypeError("VerilogRenderer.render requires VerilogRenderIR")
        lowered = render_ir.design
        previous_storage_kinds = self._storage_kinds
        previous_operators = self._assignment_operators
        self._storage_kinds = render_ir.storage_kinds
        self._assignment_operators = render_ir.assignment_operators
        try:
            modules = [self._render_module(module) for module in lowered.modules]
            text = "\n\n".join(modules)
            if lowered.leading_comments:
                text = "\n".join(self._render_comment_group(lowered.leading_comments)) + "\n" + text
            if lowered.trailing_comments:
                text += "\n" + "\n".join(self._render_comment_group(lowered.trailing_comments))
            return self._normalize_output(text)
        finally:
            self._storage_kinds = previous_storage_kinds
            self._assignment_operators = previous_operators

    def _render_module(self, module: Module) -> str:
        parameters = [self._render_parameter_entry(item) for item in module.parameters]
        ports = [self._render_port_entry(item) for item in module.ports]
        declarations = [self._render_declaration(item, 0) for item in module.signals]
        declarations.extend(self._render_declaration(item, 0) for item in module.variables)

        body_items: list[str] = []
        genvars = self._collect_genvars(module.items)
        declarations_in_scope = {item.name for item in module.parameters}
        declarations_in_scope.update(item.name for item in module.ports)
        declarations_in_scope.update(item.name for item in module.signals)
        declarations_in_scope.update(item.name for item in module.variables)
        declarations_in_scope.update(self._collect_item_declaration_names(module.items))
        collisions = [name for name in genvars if name in declarations_in_scope]
        if collisions:
            raise GenerationError(
                f"generate index {collisions[0]!r} conflicts with a declaration",
                code="HDLX-GEN-GENVAR-COLLISION",
                source_span=module.source_span,
            )
        for item in module.items:
            if isinstance(item, ForGenerate | IfGenerate):
                region = {
                    "kind": "generate_region",
                    "indent": "",
                    "genvars": self._collect_genvars([item]),
                    "body": self._render_item(item, 1),
                }
                body_items.append(self._item_template.render(item=region).strip("\r\n"))
            else:
                body_items.append(self._render_item(item, 0))

        rendered = self._module_template.render(
            module={
                "name": module.name,
                "parameters": parameters,
                "ports": ports,
                "declarations": declarations,
                "body_items": body_items,
            }
        ).strip("\r\n")
        return self._wrap_comments(module, rendered, 0)

    def _render_parameter_entry(self, parameter: Parameter) -> dict[str, Any]:
        if parameter.default is None:
            raise GenerationError(
                f"parameter {parameter.name!r} has no default value",
                code="HDLX-GEN-PARAMETER-DEFAULT",
                source_span=parameter.source_span,
            )
        return {
            "declaration": self._render_parameter_declaration(parameter),
            "leading_comments": self._render_comment_group(parameter.leading_comments),
            "trailing_comments": self._render_comment_group(parameter.trailing_comments),
        }

    def _render_port_entry(self, port: Port) -> dict[str, Any]:
        return {
            "declaration": self._render_port_declaration(port),
            "leading_comments": self._render_comment_group(port.leading_comments),
            "trailing_comments": self._render_comment_group(port.trailing_comments),
        }

    def _render_parameter_declaration(self, parameter: Parameter) -> str:
        type_text = self._render_parameter_type(parameter.rtl_type)
        prefix = "parameter" if not type_text else f"parameter {type_text}"
        assert parameter.default is not None
        return f"{prefix} {parameter.name} = {self._render_expression(parameter.default)}"

    def _render_port_declaration(self, port: Port) -> str:
        direction = port.direction.value
        if isinstance(port.rtl_type, IntegerType):
            raise GenerationError(
                f"integer port {port.name!r} is outside the Verilog-2001 MVP",
                code="HDLX-GEN-PORT-TYPE",
                source_span=port.source_span,
            )

        storage = self._storage_kind(port)
        suffix = self._render_packed_type(port.rtl_type)
        return " ".join(
            part for part in (direction, storage.value, suffix, port.name) if part
        )

    def _render_declaration(self, declaration: Signal | Variable, level: int) -> str:
        if declaration.initial_value is not None:
            raise GenerationError(
                f"declaration initializer for {declaration.name!r} is outside the MVP",
                code="HDLX-GEN-DECLARATION-INITIALIZER",
                source_span=declaration.source_span,
            )
        storage = self._storage_kind(declaration)
        if storage is VerilogStorageKind.INTEGER:
            core = f"{self._indent * level}integer {declaration.name};"
        else:
            suffix = self._render_packed_type(declaration.rtl_type)
            pieces = [storage.value]
            if suffix:
                pieces.append(suffix)
            pieces.append(declaration.name)
            core = f"{self._indent * level}{' '.join(pieces)};"
        return self._wrap_comments(declaration, core, level)

    def _storage_kind(self, declaration: Port | Signal | Variable) -> VerilogStorageKind:
        storage = self._storage_kinds.get(id(declaration))
        if storage is None:
            raise GenerationError(
                "Verilog render IR 缺少声明存储类别；必须先执行 Verilog lowering",
                code="HDLX-GEN-LOWERING-INCOMPLETE",
                source_span=declaration.source_span,
            )
        return storage

    def _render_parameter_type(self, rtl_type: object) -> str:
        if isinstance(rtl_type, IntegerType):
            return "integer"
        return self._render_packed_type(rtl_type)

    def _render_packed_type(self, rtl_type: object) -> str:
        if isinstance(rtl_type, VectorType):
            pieces = []
            if rtl_type.signed:
                pieces.append("signed")
            pieces.append(self._render_range(rtl_type.range))
            return " ".join(pieces)
        if isinstance(rtl_type, ScalarType):
            return "signed" if rtl_type.signed else ""
        if isinstance(rtl_type, BooleanType):
            return ""
        raise GenerationError(
            f"unsupported RTL type {type(rtl_type).__name__}",
            code="HDLX-GEN-TYPE",
            source_span=getattr(rtl_type, "source_span", None),
        )

    def _render_range(self, value: VectorRange) -> str:
        return f"[{self._render_bound(value.left, 2)}:{self._render_bound(value.right, 2)}]"

    def _render_bound(self, value: object, parent_precedence: int = 0) -> str:
        if isinstance(value, bool):
            raise GenerationError(
                "boolean cannot be used as a vector bound",
                code="HDLX-GEN-RANGE-BOUND",
            )
        if isinstance(value, int):
            return str(value)
        return self._render_expression(value, parent_precedence)

    def _render_expression(self, expression: object, parent_precedence: int = 0) -> str:
        if isinstance(expression, Identifier):
            return expression.name
        if isinstance(expression, Literal):
            return self._render_literal(expression)
        if isinstance(expression, UnaryExpr):
            precedence = 13
            operand = self._render_expression(expression.operand, precedence)
            text = f"{_UNARY_OPERATORS[expression.operator]}{operand}"
            return f"({text})" if precedence < parent_precedence else text
        if isinstance(expression, BinaryExpr):
            if expression.operator is BinaryOperator.MODULO:
                raise GenerationError(
                    "canonical modulo semantics cannot be represented by Verilog "
                    "remainder for negative operands",
                    code="HDLX-GEN-MODULO-SEMANTICS",
                    source_span=expression.source_span,
                )
            operator, precedence = _BINARY_OPERATORS[expression.operator]
            if expression.operator is BinaryOperator.POWER:
                left = self._render_expression(expression.left, precedence + 1)
                right = self._render_expression(expression.right, precedence)
            else:
                left = self._render_expression(expression.left, precedence)
                right = self._render_expression(expression.right, precedence + 1)
            text = f"{left} {operator} {right}"
            return f"({text})" if precedence < parent_precedence else text
        if isinstance(expression, TernaryExpr):
            precedence = 1
            condition = self._render_expression(expression.condition, precedence + 1)
            when_true = self._render_expression(expression.when_true, precedence)
            when_false = self._render_expression(expression.when_false, precedence)
            text = f"{condition} ? {when_true} : {when_false}"
            return f"({text})" if precedence < parent_precedence else text
        if isinstance(expression, Concatenation):
            return "{" + ", ".join(self._render_expression(item) for item in expression.parts) + "}"
        if isinstance(expression, Index):
            self._validate_select_base(expression.value, expression)
            value = self._render_expression(expression.value, 14)
            index = self._render_expression(expression.index)
            return f"{value}[{index}]"
        if isinstance(expression, Slice):
            self._validate_select_base(expression.value, expression)
            value = self._render_expression(expression.value, 14)
            left = self._render_expression(expression.left, 2)
            right = self._render_expression(expression.right, 2)
            return f"{value}[{left}:{right}]"
        if isinstance(expression, FunctionCall):
            arguments = ", ".join(self._render_expression(item) for item in expression.arguments)
            return f"{expression.function.name}({arguments})"
        raise GenerationError(
            f"unsupported expression {type(expression).__name__}",
            code="HDLX-GEN-EXPRESSION",
            source_span=getattr(expression, "source_span", None),
        )

    @staticmethod
    def _validate_select_base(value: object, expression: object) -> None:
        if isinstance(value, Identifier | Index):
            return
        raise GenerationError(
            "Verilog-2001 cannot safely select from a compound expression",
            code="HDLX-GEN-COMPOUND-SELECT",
            source_span=getattr(expression, "source_span", None),
        )

    def _render_literal(self, literal: Literal) -> str:
        value = literal.value
        if isinstance(value, bool):
            return "1'b1" if value else "1'b0"
        if isinstance(value, int):
            if literal.bit_width is None:
                return str(value)
            signed = "s" if literal.signed else ""
            if value < 0:
                return f"-{literal.bit_width}'{signed}d{abs(value)}"
            return f"{literal.bit_width}'{signed}d{value}"

        if literal.literal_kind is LiteralKind.STRING:
            return json.dumps(value, ensure_ascii=False)
        if literal.literal_kind is LiteralKind.BOOLEAN:
            lowered = value.casefold()
            if lowered in ("true", "false"):
                return "1'b1" if lowered == "true" else "1'b0"
            self._raise_literal_error(literal)
        if literal.literal_kind is LiteralKind.INTEGER:
            if re.fullmatch(r"[+-]?[0-9][0-9_]*", value):
                return value
            self._raise_literal_error(literal)
        if literal.literal_kind is LiteralKind.BIT:
            return self._render_bit_literal(value, literal.bit_width or 1, literal)
        if literal.literal_kind is LiteralKind.BIT_VECTOR:
            bits = self._strip_source_quotes(value)
            width = literal.bit_width or len(bits.replace("_", ""))
            return self._render_bit_literal(bits, width, literal)

        stripped = self._strip_source_quotes(value)
        if re.fullmatch(r"[+-]?[0-9][0-9_]*", stripped):
            return stripped
        if re.fullmatch(r"[01xXzZ_]+", stripped):
            width = literal.bit_width or len(stripped.replace("_", ""))
            return self._render_bit_literal(stripped, width, literal)
        self._raise_literal_error(literal)
        raise AssertionError("unreachable")

    def _render_bit_literal(self, value: str, width: int, literal: Literal) -> str:
        bits = self._strip_source_quotes(value).lower()
        if not re.fullmatch(r"[01xz_]+", bits):
            self._raise_literal_error(literal)
        signed = "s" if literal.signed else ""
        return f"{width}'{signed}b{bits}"

    @staticmethod
    def _strip_source_quotes(value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            return value[1:-1]
        return value

    @staticmethod
    def _raise_literal_error(literal: Literal) -> None:
        raise GenerationError(
            f"literal {literal.value!r} has no safe Verilog-2001 representation",
            code="HDLX-GEN-LITERAL",
            source_span=literal.source_span,
        )

    def _render_statement(self, statement: object, level: int) -> str:
        indent = self._indent * level
        child_indent = self._indent * (level + 1)
        if isinstance(statement, ProceduralAssignment):
            operator = self._assignment_operators.get(id(statement))
            if operator is None:
                raise GenerationError(
                    "Verilog render IR 缺少过程赋值操作符；必须先执行 Verilog lowering",
                    code="HDLX-GEN-LOWERING-INCOMPLETE",
                    source_span=statement.source_span,
                )
            context: dict[str, Any] = {
                "kind": "assignment",
                "indent": indent,
                "target": self._render_expression(statement.target),
                "operator": operator.value,
                "value": self._render_expression(statement.value),
            }
        elif isinstance(statement, IfStatement):
            context = {
                "kind": "if",
                "indent": indent,
                "condition": self._render_expression(statement.condition),
                "then_body": self._render_statement_body(statement.then_body, level + 1),
                "else_body": (
                    self._render_statement_body(statement.else_body, level + 1)
                    if statement.else_body
                    else ""
                ),
            }
        elif isinstance(statement, CaseStatement):
            alternatives = []
            for alternative in statement.alternatives:
                alternatives.append(
                    {
                        "indent": child_indent,
                        "selectors": [
                            self._render_expression(item) for item in alternative.selectors
                        ],
                        "body": self._render_statement_body(alternative.body, level + 2),
                    }
                )
            context = {
                "kind": "case",
                "indent": indent,
                "expression": self._render_expression(statement.expression),
                "alternatives": alternatives,
                "default_body": (
                    self._render_statement_body(statement.default_body, level + 2)
                    if statement.default_body
                    else ""
                ),
                "child_indent": child_indent,
            }
        elif isinstance(statement, ForStatement):
            start = self._render_bound(statement.range.left)
            stop = self._render_bound(statement.range.right, 9)
            if statement.range.direction is RangeDirection.ASCENDING:
                condition = f"{statement.index_name} <= {stop}"
                step = f"{statement.index_name} = {statement.index_name} + 1"
            else:
                condition = f"{statement.index_name} >= {stop}"
                step = f"{statement.index_name} = {statement.index_name} - 1"
            context = {
                "kind": "for",
                "indent": indent,
                "index": statement.index_name,
                "start": start,
                "condition": condition,
                "step": step,
                "body": self._render_statement_body(statement.body, level + 1),
            }
        elif isinstance(statement, BlockStatement):
            context = {
                "kind": "block",
                "indent": indent,
                "label": statement.label,
                "body": self._render_statement_body(statement.statements, level + 1),
            }
        elif isinstance(statement, NullStatement):
            context = {"kind": "null", "indent": indent}
        elif isinstance(statement, ContinuousAssignment):
            raise GenerationError(
                "continuous assignment cannot be rendered inside a process",
                code="HDLX-GEN-CONTINUOUS-IN-PROCESS",
                source_span=statement.source_span,
            )
        else:
            raise GenerationError(
                f"unsupported statement {type(statement).__name__}",
                code="HDLX-GEN-STATEMENT",
                source_span=getattr(statement, "source_span", None),
            )
        core = self._statement_template.render(statement=context).strip("\r\n")
        return self._wrap_comments(statement, core, level)

    def _render_statement_body(self, statements: Sequence[object], level: int) -> str:
        if not statements:
            return f"{self._indent * level};"
        return "\n".join(self._render_statement(item, level) for item in statements)

    def _render_item(self, item: object, level: int) -> str:
        indent = self._indent * level
        if isinstance(item, Signal | Variable):
            return self._render_declaration(item, level)
        if isinstance(item, ContinuousAssignment):
            context: dict[str, Any] = {
                "kind": "continuous_assignment",
                "indent": indent,
                "target": self._render_expression(item.target),
                "value": self._render_expression(item.value),
            }
        elif isinstance(item, CombinationalProcess):
            if not item.sensitivity:
                header = "always @(*)"
            else:
                sensitivity = " or ".join(
                    self._render_expression(expression) for expression in item.sensitivity
                )
                header = f"always @({sensitivity})"
            context = {
                "kind": "process",
                "indent": indent,
                "header": header,
                "label": item.label,
                "body": self._render_statement_body(item.body, level + 1),
            }
        elif isinstance(item, SequentialProcess):
            header, statements = self._lower_sequential_process(item, level)
            context = {
                "kind": "process",
                "indent": indent,
                "header": header,
                "label": item.label,
                "body": statements,
            }
        elif isinstance(item, Instance):
            context = self._render_instance_context(item, level)
        elif isinstance(item, ForGenerate):
            start = self._render_bound(item.range.left)
            stop = self._render_bound(item.range.right, 9)
            if item.range.direction is RangeDirection.ASCENDING:
                condition = f"{item.index_name} <= {stop}"
                step = f"{item.index_name} = {item.index_name} + 1"
            else:
                condition = f"{item.index_name} >= {stop}"
                step = f"{item.index_name} = {item.index_name} - 1"
            context = {
                "kind": "for_generate",
                "indent": indent,
                "label": item.label,
                "index": item.index_name,
                "start": start,
                "condition": condition,
                "step": step,
                "body": self._render_item_body(item.body, level + 1),
            }
        elif isinstance(item, IfGenerate):
            context = {
                "kind": "if_generate",
                "indent": indent,
                "label": item.label,
                "condition": self._render_expression(item.condition),
                "then_body": self._render_item_body(item.then_body, level + 1),
                "else_body": (
                    self._render_item_body(item.else_body, level + 1) if item.else_body else ""
                ),
            }
        else:
            raise GenerationError(
                f"unsupported module item {type(item).__name__}",
                code="HDLX-GEN-MODULE-ITEM",
                source_span=getattr(item, "source_span", None),
            )
        core = self._item_template.render(item=context).strip("\r\n")
        return self._wrap_comments(item, core, level)

    def _lower_sequential_process(self, process: SequentialProcess, level: int) -> tuple[str, str]:
        clock_edge = "posedge" if process.edge is EdgeKind.POSITIVE else "negedge"
        clock = self._render_expression(process.clock)
        header = f"always @({clock_edge} {clock}"
        if process.reset is not None and process.reset.kind is ResetKind.ASYNCHRONOUS:
            reset_edge = "posedge" if process.reset.active_level is ActiveLevel.HIGH else "negedge"
            header += f" or {reset_edge} {self._render_expression(process.reset.signal)}"
        header += ")"

        if process.reset is None:
            return header, self._render_statement_body(process.body, level + 1)

        reset_signal = self._render_expression(process.reset.signal, 13)
        condition = (
            reset_signal if process.reset.active_level is ActiveLevel.HIGH else f"!{reset_signal}"
        )
        reset_if = {
            "kind": "if",
            "indent": self._indent * (level + 1),
            "condition": condition,
            "then_body": self._render_statement_body(process.reset_body, level + 2),
            "else_body": self._render_statement_body(process.body, level + 2),
        }
        rendered = self._statement_template.render(statement=reset_if).strip("\r\n")
        return header, rendered

    def _render_instance_context(self, instance: Instance, level: int) -> dict[str, Any]:
        parameters = [
            self._render_binding_context(binding, level + 1)
            for binding in instance.parameter_bindings
        ]
        ports = [
            self._render_binding_context(binding, level + 1) for binding in instance.port_bindings
        ]
        return {
            "kind": "instance",
            "indent": self._indent * level,
            "continuation_indent": self._indent * level,
            "unit": instance.referenced_unit,
            "name": instance.name,
            "parameters": parameters,
            "ports": ports,
        }

    def _render_binding_context(
        self, binding: ParameterBinding | PortBinding, level: int
    ) -> dict[str, Any]:
        value = binding.value
        rendered_value = "" if value is None else self._render_expression(value)
        if value is None and binding.formal is None:
            rendered_value = "/* open */"
        return {
            "indent": self._indent * level,
            "formal": binding.formal,
            "value": rendered_value,
            "leading_comments": self._render_comment_group(binding.leading_comments),
            "trailing_comments": self._render_comment_group(binding.trailing_comments),
        }

    def _render_item_body(self, items: Sequence[object], level: int) -> str:
        if not items:
            return f"{self._indent * level};"
        return "\n".join(self._render_item(item, level) for item in items)

    def _collect_genvars(self, items: Sequence[object]) -> list[str]:
        result: list[str] = []

        def visit(nodes: Sequence[object]) -> None:
            for node in nodes:
                if isinstance(node, ForGenerate):
                    if node.index_name in result:
                        raise GenerationError(
                            f"generate index {node.index_name!r} is not unique in module scope",
                            code="HDLX-GEN-GENVAR-COLLISION",
                            source_span=node.source_span,
                        )
                    result.append(node.index_name)
                    visit(node.body)
                elif isinstance(node, IfGenerate):
                    visit(node.then_body)
                    visit(node.else_body)

        visit(items)
        return result

    def _collect_item_declaration_names(self, items: Sequence[object]) -> set[str]:
        names: set[str] = set()
        for item in items:
            if isinstance(item, Signal | Variable):
                names.add(item.name)
            elif isinstance(item, ForGenerate):
                names.update(self._collect_item_declaration_names(item.body))
            elif isinstance(item, IfGenerate):
                names.update(self._collect_item_declaration_names(item.then_body))
                names.update(self._collect_item_declaration_names(item.else_body))
        return names

    def _render_comment_group(self, comments: list[Comment]) -> list[str]:
        result: list[str] = []
        for comment in comments:
            text = comment.text.rstrip("\r\n").replace("*/", "* /")
            lines = text.splitlines() or [""]
            if comment.kind is CommentKind.BLOCK:
                if len(lines) == 1:
                    result.append(f"/* {lines[0]} */")
                else:
                    result.append(f"/* {lines[0]}")
                    result.extend(f" * {line}" for line in lines[1:])
                    result.append(" */")
            else:
                marker = "///" if comment.kind is CommentKind.DOC else "//"
                result.extend(f"{marker} {line}" for line in lines)
        return result

    def _wrap_comments(self, node: IRNode, core: str, level: int) -> str:
        indent = self._indent * level
        parts: list[str] = []
        leading = self._render_comment_group(node.leading_comments)
        trailing = self._render_comment_group(node.trailing_comments)
        if leading:
            parts.extend(f"{indent}{line}" for line in leading)
        parts.append(core)
        if trailing:
            parts.extend(f"{indent}{line}" for line in trailing)
        return "\n".join(parts)

    @staticmethod
    def _normalize_output(text: str) -> str:
        lines = [line.rstrip() for line in text.splitlines()]
        normalized: list[str] = []
        blank = False
        for line in lines:
            if not line:
                if blank:
                    continue
                blank = True
            else:
                blank = False
            normalized.append(line)
        return "\n".join(normalized).strip("\n") + "\n"


class VerilogGenerator(Generator):
    """v0.1 兼容 facade；新代码应显式调用 lowering 与 renderer。"""

    def __init__(
        self,
        *,
        template_directory: Path | None = None,
        driver_analysis: DriverAnalysis | None = None,
        name_style: NameStyle = NameStyle.PRESERVE,
        indent: str = "    ",
    ) -> None:
        self._lowering = VerilogLowering(
            name_style=name_style,
            driver_analysis=driver_analysis,
        )
        self._renderer = VerilogRenderer(
            template_directory=template_directory,
            indent=indent,
        )
        self._last_name_mappings: dict[str, str] = {}

    @property
    def name_mappings(self) -> dict[str, str]:
        """返回上一次生成使用的作用域限定名称映射。"""

        return dict(self._last_name_mappings)

    def lower(self, design: Design) -> VerilogRenderIR:
        """兼容 facade 暴露的显式 lowering 入口。"""

        render_ir = self._lowering.lower(design)
        self._last_name_mappings = dict(render_ir.name_mappings)
        return render_ir

    def render(self, render_ir: VerilogRenderIR) -> str:
        """渲染已完成 lowering 的目标 IR。"""

        self._last_name_mappings = dict(render_ir.name_mappings)
        return self._renderer.render(render_ir)

    def generate(self, design: Design) -> str:
        """兼容旧 API：依次执行 lowering 与 render。"""

        return self.render(self.lower(design))

    def generate_lowered(self, lowered: Design) -> str:
        """兼容旧 API：渲染已由调用方降低的 canonical Design。"""

        return self.render(self._lowering.wrap_lowered(lowered))
