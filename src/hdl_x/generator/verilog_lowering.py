"""Canonical Design 到 Verilog render IR 的显式 lowering。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from hdl_x.ir import (
    AssignmentKind,
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    Design,
    DriverKind,
    ForGenerate,
    ForStatement,
    IfGenerate,
    IfStatement,
    IntegerType,
    ModuleItem,
    PortDirection,
    ProceduralAssignment,
    SequentialProcess,
    Signal,
    StatementNode,
    Variable,
)
from hdl_x.transformer.identifier_resolver import DesignIdentifierResolver, NameStyle
from hdl_x.transformer.type_lowering import DriverAnalysis

from .verilog_ir import (
    VerilogAssignmentOperator,
    VerilogRenderIR,
    VerilogStorageKind,
)


class VerilogLowering:
    """集中执行 Verilog 标识符与 net/reg driver 决策。"""

    def __init__(
        self,
        *,
        name_style: NameStyle = NameStyle.PRESERVE,
        driver_analysis: DriverAnalysis | None = None,
        source_case_sensitive: bool = False,
    ) -> None:
        self._name_style = name_style
        self._driver_analysis = driver_analysis or DriverAnalysis()
        self._source_case_sensitive = source_case_sensitive

    def lower(self, design: Design) -> VerilogRenderIR:
        """返回独立目标 IR，不修改调用方传入的 canonical Design。"""

        resolver = DesignIdentifierResolver(
            self._name_style,
            case_sensitive=self._source_case_sensitive,
        )
        resolved = resolver.lower(design)
        lowered = self._driver_analysis.lower(resolved)
        return self.wrap_lowered(lowered, name_mappings=resolver.mappings)

    def wrap_lowered(
        self,
        design: Design,
        *,
        name_mappings: Mapping[str, str] | None = None,
    ) -> VerilogRenderIR:
        """为兼容调用方提供只补目标赋值决策的 render IR 包装。"""

        return VerilogRenderIR(
            design=design,
            name_mappings={} if name_mappings is None else name_mappings,
            storage_kinds=_storage_kinds(design),
            assignment_operators=_assignment_operators(design),
        )


def _storage_kinds(design: Design) -> dict[int, VerilogStorageKind]:
    kinds: dict[int, VerilogStorageKind] = {}
    for module in design.modules:
        for port in module.ports:
            if isinstance(port.rtl_type, IntegerType):
                kinds[id(port)] = VerilogStorageKind.INTEGER
            elif port.direction in (PortDirection.INPUT, PortDirection.INOUT):
                kinds[id(port)] = VerilogStorageKind.WIRE
            elif port.driver_kind is DriverKind.PROCEDURAL:
                kinds[id(port)] = VerilogStorageKind.REG
            else:
                kinds[id(port)] = VerilogStorageKind.WIRE
        for declaration in (*module.signals, *module.variables):
            _record_declaration_storage(declaration, kinds)
        _collect_item_storage_kinds(module.items, kinds)
    return kinds


def _collect_item_storage_kinds(
    items: Sequence[ModuleItem],
    kinds: dict[int, VerilogStorageKind],
) -> None:
    for item in items:
        if isinstance(item, Signal | Variable):
            _record_declaration_storage(item, kinds)
        elif isinstance(item, ForGenerate):
            _collect_item_storage_kinds(item.body, kinds)
        elif isinstance(item, IfGenerate):
            _collect_item_storage_kinds(item.then_body, kinds)
            _collect_item_storage_kinds(item.else_body, kinds)


def _record_declaration_storage(
    declaration: Signal | Variable,
    kinds: dict[int, VerilogStorageKind],
) -> None:
    if isinstance(declaration.rtl_type, IntegerType):
        kinds[id(declaration)] = VerilogStorageKind.INTEGER
    elif isinstance(declaration, Variable):
        kinds[id(declaration)] = VerilogStorageKind.REG
    elif declaration.driver_kind is DriverKind.PROCEDURAL:
        kinds[id(declaration)] = VerilogStorageKind.REG
    else:
        kinds[id(declaration)] = VerilogStorageKind.WIRE


def _assignment_operators(
    design: Design,
) -> dict[int, VerilogAssignmentOperator]:
    operators: dict[int, VerilogAssignmentOperator] = {}
    for module in design.modules:
        _collect_item_assignment_operators(module.items, operators)
    return operators


def _collect_item_assignment_operators(
    items: Sequence[ModuleItem],
    operators: dict[int, VerilogAssignmentOperator],
) -> None:
    for item in items:
        if isinstance(item, CombinationalProcess):
            _collect_statement_assignment_operators(item.body, operators)
        elif isinstance(item, SequentialProcess):
            _collect_statement_assignment_operators(item.reset_body, operators)
            _collect_statement_assignment_operators(item.body, operators)
        elif isinstance(item, ForGenerate):
            _collect_item_assignment_operators(item.body, operators)
        elif isinstance(item, IfGenerate):
            _collect_item_assignment_operators(item.then_body, operators)
            _collect_item_assignment_operators(item.else_body, operators)


def _collect_statement_assignment_operators(
    statements: Sequence[StatementNode],
    operators: dict[int, VerilogAssignmentOperator],
) -> None:
    for statement in statements:
        if isinstance(statement, ProceduralAssignment):
            operators[id(statement)] = (
                VerilogAssignmentOperator.BLOCKING
                if statement.assignment_kind is AssignmentKind.BLOCKING
                else VerilogAssignmentOperator.NON_BLOCKING
            )
        elif isinstance(statement, IfStatement):
            _collect_statement_assignment_operators(statement.then_body, operators)
            _collect_statement_assignment_operators(statement.else_body, operators)
        elif isinstance(statement, CaseStatement):
            for alternative in statement.alternatives:
                _collect_statement_assignment_operators(alternative.body, operators)
            _collect_statement_assignment_operators(statement.default_body, operators)
        elif isinstance(statement, ForStatement):
            _collect_statement_assignment_operators(statement.body, operators)
        elif isinstance(statement, BlockStatement):
            _collect_statement_assignment_operators(statement.statements, operators)


__all__ = ["VerilogLowering"]
