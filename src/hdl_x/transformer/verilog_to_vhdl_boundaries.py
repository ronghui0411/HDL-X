"""Verilog-2001 到 VHDL-2008 的保守语义边界分析。"""

from __future__ import annotations

from collections.abc import Iterable

from hdl_x.diagnostics import Diagnostic, DiagnosticSeverity, SemanticError
from hdl_x.ir import (
    BinaryExpr,
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    Concatenation,
    ContinuousAssignment,
    Design,
    ForGenerate,
    ForStatement,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Literal,
    LiteralKind,
    ProceduralAssignment,
    SequentialProcess,
    Slice,
    TernaryExpr,
    UnaryExpr,
)


class VerilogToVhdlSemanticBoundaryAnalysis:
    """拒绝不安全 driver/meta 结构，并报告已知调度与四态边界。"""

    def analyze(self, design: Design) -> tuple[Diagnostic, ...]:
        diagnostics: list[Diagnostic] = []
        for module in design.modules:
            drivers: dict[str, list[object]] = {}
            for item in self._iter_items(module.items):
                targets = self._item_targets(item)
                for target in targets:
                    drivers.setdefault(target, []).append(item)

                if self._item_contains_meta(item, value="z"):
                    raise SemanticError(
                        "显式 Z/high-impedance 无法在当前 VHDL signal resolution "
                        "策略中保证等价",
                        code="HDLX-V2V-TRISTATE",
                        source_span=getattr(item, "source_span", None),
                        suggestion="将三态边界保留在顶层，或等待显式 resolved-driver 支持。",
                    )
                if self._item_contains_meta(item, value="x"):
                    diagnostics.append(
                        self._warning(
                            "HDLX-V2V-META-VALUE",
                            f"模块 {module.name} 包含显式 X；VHDL std_logic 可表示该值，"
                            "但后续运算传播不声明逐调度等价。",
                            item,
                        )
                    )
                if self._item_contains_unsized_binary(item):
                    diagnostics.append(
                        self._warning(
                            "HDLX-V2V-UNSIZED-SIZING",
                            f"模块 {module.name} 的表达式混用 unsized integer；Verilog "
                            "self-determined sizing 与 VHDL overload/target sizing "
                            "不声明普遍等价。",
                            item,
                            suggestion="使用与目标位宽和 signedness 一致的显式 sized literal。",
                        )
                    )

                if isinstance(item, CombinationalProcess):
                    diagnostics.append(
                        self._warning(
                            "HDLX-V2V-TIME-ZERO",
                            f"模块 {module.name} 的 ordinary combinational always 将映射为 "
                            "VHDL process(all)；time-zero 初次执行时刻不保证等价。",
                            item,
                            suggestion="差分仿真应在输入变化并经过 delta-cycle 后开始比较。",
                        )
                    )
                elif isinstance(item, SequentialProcess):
                    diagnostics.append(
                        self._warning(
                            "HDLX-V2V-EDGE-META",
                            f"模块 {module.name} 的 edge always 只保证稳定 0/1 clock/reset "
                            "边沿；X/Z transition 与 rising_edge/falling_edge 不保证等价。",
                            item,
                            suggestion="验证环境不得在 clock/reset 上驱动 X/Z transition。",
                        )
                    )
                    if item.reset is None:
                        diagnostics.append(
                            self._warning(
                                "HDLX-V2V-INITIAL-STATE",
                                f"模块 {module.name} 的无复位时序状态在 Verilog 中从 X "
                                "开始，而 VHDL std_logic 从 U 开始；不声明初始仿真等价。",
                                item,
                                suggestion="在比较前施加约束，或为状态增加受支持的 reset。",
                            )
                        )

            for target, sources in drivers.items():
                if len(sources) > 1:
                    raise SemanticError(
                        f"signal {target!r} 有 {len(sources)} 个独立 driver；当前 V2V MVP "
                        "不猜测 resolved/unresolved 映射",
                        code="HDLX-V2V-MULTIPLE-DRIVER",
                        source_span=getattr(sources[1], "source_span", None),
                        suggestion="合并为单一 driver，或等待显式 resolution policy。",
                    )
        return tuple(diagnostics)

    @staticmethod
    def _warning(
        code: str,
        message: str,
        node: object,
        *,
        suggestion: str | None = None,
    ) -> Diagnostic:
        return Diagnostic(
            code=code,
            message=message,
            severity=DiagnosticSeverity.WARNING,
            source_span=getattr(node, "source_span", None),
            suggestion=suggestion,
        )

    @classmethod
    def _iter_items(cls, items: Iterable[object]) -> Iterable[object]:
        for item in items:
            if isinstance(item, ForGenerate):
                yield from cls._iter_items(item.body)
            elif isinstance(item, IfGenerate):
                yield from cls._iter_items(item.then_body)
                yield from cls._iter_items(item.else_body)
            else:
                yield item

    @classmethod
    def _item_targets(cls, item: object) -> set[str]:
        if isinstance(item, ContinuousAssignment):
            return cls._target_names(item.target)
        if isinstance(item, CombinationalProcess):
            return cls._statement_targets(item.body)
        if isinstance(item, SequentialProcess):
            return cls._statement_targets((*item.reset_body, *item.body))
        return set()

    @classmethod
    def _statement_targets(cls, statements: Iterable[object]) -> set[str]:
        result: set[str] = set()
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                result.update(cls._target_names(statement.target))
            elif isinstance(statement, IfStatement):
                result.update(cls._statement_targets(statement.then_body))
                result.update(cls._statement_targets(statement.else_body))
            elif isinstance(statement, CaseStatement):
                for alternative in statement.alternatives:
                    result.update(cls._statement_targets(alternative.body))
                result.update(cls._statement_targets(statement.default_body))
            elif isinstance(statement, BlockStatement):
                result.update(cls._statement_targets(statement.statements))
        return result

    @classmethod
    def _item_expressions(cls, item: object) -> Iterable[object]:
        if isinstance(item, ContinuousAssignment):
            yield item.value
        elif isinstance(item, CombinationalProcess):
            yield from cls._statement_expressions(item.body)
        elif isinstance(item, SequentialProcess):
            yield from cls._statement_expressions((*item.reset_body, *item.body))

    @classmethod
    def _statement_expressions(cls, statements: Iterable[object]) -> Iterable[object]:
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                yield statement.value
            elif isinstance(statement, IfStatement):
                yield statement.condition
                yield from cls._statement_expressions(statement.then_body)
                yield from cls._statement_expressions(statement.else_body)
            elif isinstance(statement, CaseStatement):
                yield statement.expression
                for alternative in statement.alternatives:
                    yield from alternative.selectors
                    yield from cls._statement_expressions(alternative.body)
                yield from cls._statement_expressions(statement.default_body)
            elif isinstance(statement, ForStatement):
                yield statement.range.left
                yield statement.range.right
                yield from cls._statement_expressions(statement.body)
            elif isinstance(statement, BlockStatement):
                yield from cls._statement_expressions(statement.statements)

    @classmethod
    def _item_contains_meta(cls, item: object, *, value: str) -> bool:
        return any(
            cls._contains_meta(expression, value=value)
            for expression in cls._item_expressions(item)
        )

    @classmethod
    def _item_contains_unsized_binary(cls, item: object) -> bool:
        return any(
            cls._contains_unsized_binary(expression)
            for expression in cls._item_expressions(item)
        )

    @classmethod
    def _contains_unsized_binary(cls, expression: object) -> bool:
        if isinstance(expression, BinaryExpr):
            if cls._contains_unsized_literal(expression):
                return True
            return cls._contains_unsized_binary(
                expression.left
            ) or cls._contains_unsized_binary(expression.right)
        if isinstance(expression, UnaryExpr):
            return cls._contains_unsized_binary(expression.operand)
        if isinstance(expression, TernaryExpr):
            return any(
                cls._contains_unsized_binary(part)
                for part in (
                    expression.condition,
                    expression.when_true,
                    expression.when_false,
                )
            )
        if isinstance(expression, Concatenation):
            return any(cls._contains_unsized_binary(part) for part in expression.parts)
        if isinstance(expression, Index):
            return cls._contains_unsized_binary(
                expression.value
            ) or cls._contains_unsized_binary(expression.index)
        if isinstance(expression, Slice):
            return any(
                cls._contains_unsized_binary(part)
                for part in (expression.value, expression.left, expression.right)
            )
        return False

    @classmethod
    def _contains_unsized_literal(cls, expression: object) -> bool:
        if isinstance(expression, Literal):
            return (
                expression.literal_kind is LiteralKind.INTEGER
                and expression.bit_width is None
            )
        if isinstance(expression, UnaryExpr):
            return cls._contains_unsized_literal(expression.operand)
        if isinstance(expression, BinaryExpr):
            return cls._contains_unsized_literal(
                expression.left
            ) or cls._contains_unsized_literal(expression.right)
        if isinstance(expression, TernaryExpr):
            return any(
                cls._contains_unsized_literal(part)
                for part in (
                    expression.condition,
                    expression.when_true,
                    expression.when_false,
                )
            )
        if isinstance(expression, Concatenation):
            return any(cls._contains_unsized_literal(part) for part in expression.parts)
        if isinstance(expression, Index):
            return cls._contains_unsized_literal(
                expression.value
            ) or cls._contains_unsized_literal(expression.index)
        if isinstance(expression, Slice):
            return any(
                cls._contains_unsized_literal(part)
                for part in (expression.value, expression.left, expression.right)
            )
        return False
    @classmethod
    def _target_names(cls, target: object) -> set[str]:
        if isinstance(target, Identifier):
            return {target.name}
        if isinstance(target, Index | Slice):
            return cls._target_names(target.value)
        if isinstance(target, Concatenation):
            result: set[str] = set()
            for part in target.parts:
                result.update(cls._target_names(part))
            return result
        return set()

    @classmethod
    def _contains_meta(cls, expression: object, *, value: str) -> bool:
        if isinstance(expression, Literal) and isinstance(expression.value, str):
            text = expression.value.strip("'\"").replace("_", "").casefold()
            return value in text
        if isinstance(expression, UnaryExpr):
            return cls._contains_meta(expression.operand, value=value)
        if isinstance(expression, BinaryExpr):
            return cls._contains_meta(
                expression.left, value=value
            ) or cls._contains_meta(expression.right, value=value)
        if isinstance(expression, TernaryExpr):
            return any(
                cls._contains_meta(part, value=value)
                for part in (
                    expression.condition,
                    expression.when_true,
                    expression.when_false,
                )
            )
        if isinstance(expression, Concatenation):
            return any(cls._contains_meta(part, value=value) for part in expression.parts)
        if isinstance(expression, Index):
            return cls._contains_meta(
                expression.value, value=value
            ) or cls._contains_meta(expression.index, value=value)
        if isinstance(expression, Slice):
            return any(
                cls._contains_meta(part, value=value)
                for part in (expression.value, expression.left, expression.right)
            )
        return False


__all__ = ["VerilogToVhdlSemanticBoundaryAnalysis"]
