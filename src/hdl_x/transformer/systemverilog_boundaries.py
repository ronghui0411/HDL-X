"""SystemVerilog 到 Verilog-2001 的保守仿真边界诊断。"""

from __future__ import annotations

from collections.abc import Iterable

from hdl_x.diagnostics import Diagnostic, DiagnosticSeverity
from hdl_x.ir import (
    CombinationalProcess,
    Design,
    Identifier,
    IfStatement,
    SequentialProcess,
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
