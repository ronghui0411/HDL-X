"""跨 HDL 仿真模型边界的保守诊断。"""

from __future__ import annotations

from collections.abc import Iterable

from hdl_x.diagnostics import Diagnostic, DiagnosticSeverity
from hdl_x.ir import (
    BlockStatement,
    CaseStatement,
    Design,
    ForGenerate,
    ForStatement,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Module,
    ProceduralAssignment,
    RTLType,
    SequentialProcess,
    Signal,
    StatementNode,
)


class SemanticBoundaryAnalysis:
    """报告目标 HDL 无法精确保留、但不改变综合结构的语义边界。"""

    def analyze(self, design: Design) -> tuple[Diagnostic, ...]:
        """返回确定、有序且不重复的边界诊断。"""

        diagnostics: list[Diagnostic] = []
        for module in design.modules:
            scope = {
                declaration.name.casefold(): declaration.rtl_type
                for group in (module.ports, module.signals, module.variables)
                for declaration in group
            }
            self._walk_items(module, module.items, scope, diagnostics)
        return tuple(diagnostics)

    def _walk_items(
        self,
        module: Module,
        items: Iterable[object],
        scope: dict[str, RTLType],
        diagnostics: list[Diagnostic],
    ) -> None:
        for item in items:
            if isinstance(item, SequentialProcess) and item.reset is None:
                self._report_unreset_state(module, item, scope, diagnostics)
            elif isinstance(item, ForGenerate):
                nested_scope = self._extend_scope(scope, item.body)
                self._walk_items(module, item.body, nested_scope, diagnostics)
            elif isinstance(item, IfGenerate):
                then_scope = self._extend_scope(scope, item.then_body)
                else_scope = self._extend_scope(scope, item.else_body)
                self._walk_items(module, item.then_body, then_scope, diagnostics)
                self._walk_items(module, item.else_body, else_scope, diagnostics)

    @staticmethod
    def _extend_scope(scope: dict[str, RTLType], items: Iterable[object]) -> dict[str, RTLType]:
        nested = dict(scope)
        for item in items:
            if isinstance(item, Signal):
                nested[item.name.casefold()] = item.rtl_type
        return nested

    def _report_unreset_state(
        self,
        module: Module,
        process: SequentialProcess,
        scope: dict[str, RTLType],
        diagnostics: list[Diagnostic],
    ) -> None:
        targets = sorted(self._assigned_names(process.body), key=str.casefold)
        two_state = [name for name in targets if self._is_four_state(scope, name) is False]
        four_state = [name for name in targets if self._is_four_state(scope, name) is True]
        unknown = [name for name in targets if self._is_four_state(scope, name) is None]

        details: list[str] = []
        if two_state:
            details.append(
                "bit-like 状态 "
                f"{', '.join(two_state)} 的 VHDL 隐式初值为 '0'，Verilog reg 初值为 X"
            )
        if four_state:
            details.append(
                "std_logic-like 状态 "
                f"{', '.join(four_state)} 的 VHDL 隐式初值 'U' 无法由 Verilog 四态精确编码"
            )
        if unknown:
            details.append(f"状态 {', '.join(unknown)} 的初始值模型无法证明等价")
        if not details:
            details.append("该 process 的状态初始值模型无法证明等价")

        diagnostics.append(
            Diagnostic(
                code="HDLX-VHDL-INITIAL-STATE",
                message=(
                    f"模块 {module.name} 的无复位时序 process：{'；'.join(details)}；"
                    "仅承诺综合状态转移，不保证仿真开始到首次有效赋值之间的初态等价。"
                ),
                severity=DiagnosticSeverity.WARNING,
                source_span=process.source_span,
                suggestion="通过显式复位建立已知状态，并在比较仿真结果前先施加复位。",
            )
        )

    @staticmethod
    def _is_four_state(scope: dict[str, RTLType], name: str) -> bool | None:
        rtl_type = scope.get(name.casefold())
        return None if rtl_type is None else rtl_type.four_state

    def _assigned_names(self, statements: Iterable[StatementNode]) -> set[str]:
        names: set[str] = set()
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                name = self._target_name(statement.target)
                if name is not None:
                    names.add(name)
            elif isinstance(statement, IfStatement):
                names.update(self._assigned_names(statement.then_body))
                names.update(self._assigned_names(statement.else_body))
            elif isinstance(statement, CaseStatement):
                for alternative in statement.alternatives:
                    names.update(self._assigned_names(alternative.body))
                names.update(self._assigned_names(statement.default_body))
            elif isinstance(statement, ForStatement):
                names.update(self._assigned_names(statement.body))
            elif isinstance(statement, BlockStatement):
                names.update(self._assigned_names(statement.statements))
        return names

    @staticmethod
    def _target_name(target: object) -> str | None:
        while isinstance(target, Index):
            target = target.value
        return target.name if isinstance(target, Identifier) else None


__all__ = ["SemanticBoundaryAnalysis"]
