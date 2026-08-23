"""SystemVerilog 到 Verilog-2001 的保守仿真边界诊断。"""

from __future__ import annotations

from collections.abc import Iterable

from hdl_x.diagnostics import Diagnostic, DiagnosticSeverity, UnsupportedConstructError
from hdl_x.ir import (
    BinaryExpr,
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    Concatenation,
    ContinuousAssignment,
    Design,
    ForStatement,
    FunctionCall,
    Identifier,
    IfStatement,
    Index,
    ProceduralAssignment,
    SequentialProcess,
    Slice,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
)


class SystemVerilogSemanticBoundaryAnalysis:
    """报告综合结构保持、但语言级仿真不能完整等价的边界。"""

    def analyze(self, design: Design) -> tuple[Diagnostic, ...]:
        """返回与模块、item 顺序一致的结构化 warning。"""

        diagnostics: list[Diagnostic] = []
        for module in design.modules:
            for item in module.items:
                if isinstance(item, CombinationalProcess):
                    if not self._statements_have_read_dependency(item.body):
                        raise UnsupportedConstructError(
                            "always_comb 不读取任何触发表达式；降为 always @(*) 后"
                            "无法保持 time-zero 自动执行语义",
                            code="HDLX-SV-ALWAYS-COMB-NO-TRIGGER",
                            source_span=item.source_span,
                            suggestion="让组合过程显式读取输入，或改写为受支持的连续赋值。",
                        )
                    diagnostics.append(
                        Diagnostic(
                            code="HDLX-SV-ALWAYS-COMB-TIME-ZERO",
                            message=(
                                f"模块 {module.name} 的 always_comb 会降为 always @(*)；"
                                "目标不保证 SystemVerilog time-zero 自动执行语义。"
                            ),
                            severity=DiagnosticSeverity.WARNING,
                            source_span=item.source_span,
                            suggestion="差分仿真应在输入稳定并经过一个调度周期后开始采样。",
                        )
                    )
                elif isinstance(item, SequentialProcess):
                    diagnostics.append(
                        Diagnostic(
                            code="HDLX-SV-EDGE-XZ",
                            message=(
                                f"模块 {module.name} 的 edge-triggered always_ff 只承诺稳定 0/1 "
                                "clock/reset 跳变；X/Z transition 的源/目标触发语义不保证等价。"
                            ),
                            severity=DiagnosticSeverity.WARNING,
                            source_span=item.source_span,
                            suggestion="验证环境应避免在 clock/reset 上驱动 X/Z transition。",
                        )
                    )
                    if item.reset is None and self._has_unclassified_reset_candidate(item.body):
                        diagnostics.append(
                            Diagnostic(
                                code="HDLX-SV-RESET-UNCLASSIFIED",
                                message=(
                                    f"模块 {module.name} 的顶层条件疑似 reset，但未命中 v0.2 "
                                    "rst/reset 命名约定；保留为普通 clocked "
                                    "if/else，不声明 reset 分类。"
                                ),
                                severity=DiagnosticSeverity.WARNING,
                                source_span=item.source_span,
                                suggestion=(
                                    "如需 Canonical reset 语义，请使用已记录的 rst/reset 命名，"
                                    "或在验证中按普通时序控制处理。"
                                ),
                            )
                        )
        return tuple(diagnostics)

    @classmethod
    def _statements_have_read_dependency(cls, statements: Iterable[object]) -> bool:
        """只在能证明组合过程完全没有读依赖时返回 False。"""

        for statement in statements:
            if isinstance(statement, ContinuousAssignment | ProceduralAssignment):
                if cls._expression_has_identifier(statement.value):
                    return True
                if cls._target_selector_has_identifier(statement.target):
                    return True
            elif isinstance(statement, IfStatement):
                if cls._expression_has_identifier(statement.condition):
                    return True
                if cls._statements_have_read_dependency(statement.then_body):
                    return True
                if cls._statements_have_read_dependency(statement.else_body):
                    return True
            elif isinstance(statement, CaseStatement):
                if cls._expression_has_identifier(statement.expression):
                    return True
                for alternative in statement.alternatives:
                    if any(
                        cls._expression_has_identifier(selector)
                        for selector in alternative.selectors
                    ):
                        return True
                    if cls._statements_have_read_dependency(alternative.body):
                        return True
                if cls._statements_have_read_dependency(statement.default_body):
                    return True
            elif isinstance(statement, ForStatement):
                if cls._expression_has_identifier(statement.range.left):
                    return True
                if cls._expression_has_identifier(statement.range.right):
                    return True
                if cls._statements_have_read_dependency(statement.body):
                    return True
            elif isinstance(statement, BlockStatement):
                if cls._statements_have_read_dependency(statement.statements):
                    return True
            else:
                return True
        return False

    @classmethod
    def _expression_has_identifier(cls, expression: object) -> bool:
        if isinstance(expression, Identifier | FunctionCall):
            return True
        if isinstance(expression, UnaryExpr):
            return cls._expression_has_identifier(expression.operand)
        if isinstance(expression, BinaryExpr):
            return cls._expression_has_identifier(
                expression.left
            ) or cls._expression_has_identifier(expression.right)
        if isinstance(expression, TernaryExpr):
            return any(
                cls._expression_has_identifier(item)
                for item in (
                    expression.condition,
                    expression.when_true,
                    expression.when_false,
                )
            )
        if isinstance(expression, Concatenation):
            return any(cls._expression_has_identifier(item) for item in expression.parts)
        if isinstance(expression, Index):
            return cls._expression_has_identifier(
                expression.value
            ) or cls._expression_has_identifier(expression.index)
        if isinstance(expression, Slice):
            return any(
                cls._expression_has_identifier(item)
                for item in (expression.value, expression.left, expression.right)
            )
        return False

    @classmethod
    def _target_selector_has_identifier(cls, target: object) -> bool:
        if isinstance(target, Identifier):
            return False
        if isinstance(target, Index):
            return cls._target_selector_has_identifier(
                target.value
            ) or cls._expression_has_identifier(target.index)
        if isinstance(target, Slice):
            return (
                cls._target_selector_has_identifier(target.value)
                or cls._expression_has_identifier(target.left)
                or cls._expression_has_identifier(target.right)
            )
        if isinstance(target, Concatenation):
            return any(cls._target_selector_has_identifier(item) for item in target.parts)
        return cls._expression_has_identifier(target)

    @classmethod
    def _has_unclassified_reset_candidate(cls, statements: Iterable[object]) -> bool:
        statements = tuple(statements)
        if len(statements) != 1 or not isinstance(statements[0], IfStatement):
            return False
        statement = statements[0]
        if not statement.else_body:
            return False
        name = cls._condition_identifier(statement.condition)
        if name is None:
            return False
        folded = name.casefold()
        return any(token in folded for token in ("clear", "clr", "por"))

    @staticmethod
    def _condition_identifier(condition: object) -> str | None:
        if isinstance(condition, Identifier):
            return condition.name
        if (
            isinstance(condition, UnaryExpr)
            and condition.operator is UnaryOperator.LOGICAL_NOT
            and isinstance(condition.operand, Identifier)
        ):
            return condition.operand.name
        return None


__all__ = ["SystemVerilogSemanticBoundaryAnalysis"]
