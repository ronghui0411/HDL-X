"""Canonical Design 到 VHDL-2008 render IR 的显式 lowering。"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from hdl_x.diagnostics import GenerationError
from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    ContinuousAssignment,
    Design,
    EdgeKind,
    ForGenerate,
    ForStatement,
    IfGenerate,
    IfStatement,
    Instance,
    Module,
    NullStatement,
    PortDirection,
    ProceduralAssignment,
    ResetKind,
    SequentialProcess,
    Signal,
    StatementNode,
    Variable,
)
from hdl_x.transformer.identifier_resolver import NameStyle

from .vhdl_expression_lowering import VhdlExpressionLowering, VhdlNameAllocator
from .vhdl_ir import (
    VhdlAssignmentIR,
    VhdlAssociationIR,
    VhdlCaseAlternativeIR,
    VhdlCaseStatementIR,
    VhdlConcurrentAssignmentIR,
    VhdlDeclarationIR,
    VhdlDesignUnitIR,
    VhdlForGenerateIR,
    VhdlIfGenerateIR,
    VhdlIfStatementIR,
    VhdlInstanceIR,
    VhdlItemIR,
    VhdlNullStatementIR,
    VhdlProcessIR,
    VhdlRenderIR,
    VhdlStatementIR,
)


class VhdlLowering:
    """集中执行 VHDL entity/architecture/process/association 输出决策。"""

    def __init__(self, *, name_style: NameStyle = NameStyle.PRESERVE) -> None:
        self._name_style = name_style

    def lower(self, design: Design) -> VhdlRenderIR:
        """生成不携带 frontend 对象且不修改 Canonical Design 的目标 IR。"""

        unit_allocator = VhdlNameAllocator(self._name_style)
        unit_names = {
            module.name: unit_allocator.allocate(module.name) for module in design.modules
        }
        scope_names: dict[str, dict[str, str]] = {}
        scope_types: dict[str, dict[str, object]] = {}
        mappings: dict[str, str] = dict(unit_names)
        for module in design.modules:
            allocator = VhdlNameAllocator(self._name_style)
            names: dict[str, str] = {}
            rtl_types: dict[str, object] = {}
            for declaration in (
                *module.parameters,
                *module.ports,
                *module.signals,
                *module.variables,
            ):
                names[declaration.name] = allocator.allocate(declaration.name)
                rtl_types[declaration.name] = declaration.rtl_type
                mappings[f"{module.name}.{declaration.name}"] = names[declaration.name]
            scope_names[module.name] = names
            scope_types[module.name] = rtl_types

        modules = {module.name: module for module in design.modules}
        units = tuple(
            self._lower_module(
                module,
                entity_name=unit_names[module.name],
                names=scope_names[module.name],
                rtl_types=scope_types[module.name],
                modules=modules,
                unit_names=unit_names,
                scope_names=scope_names,
                mappings=mappings,
            )
            for module in design.modules
        )
        return VhdlRenderIR(design=design, units=units, name_mappings=mappings)

    def _lower_module(
        self,
        module: Module,
        *,
        entity_name: str,
        names: dict[str, str],
        rtl_types: dict[str, object],
        modules: dict[str, Module],
        unit_names: dict[str, str],
        scope_names: dict[str, dict[str, str]],
        mappings: dict[str, str],
    ) -> VhdlDesignUnitIR:
        expressions = VhdlExpressionLowering(names, rtl_types)
        generics = tuple(
            VhdlDeclarationIR(
                name=names[item.name],
                type_text=expressions.type_text(item.rtl_type),
                default_text=(
                    None if item.default is None else expressions.expression(item.default)
                ),
                leading_comments=tuple(item.leading_comments),
                trailing_comments=tuple(item.trailing_comments),
            )
            for item in module.parameters
        )
        modes = {
            PortDirection.INPUT: "in",
            PortDirection.OUTPUT: "out",
            PortDirection.INOUT: "inout",
        }
        ports = tuple(
            VhdlDeclarationIR(
                name=names[item.name],
                type_text=expressions.type_text(item.rtl_type),
                mode=modes[item.direction],
                leading_comments=tuple(item.leading_comments),
                trailing_comments=tuple(item.trailing_comments),
            )
            for item in module.ports
        )
        signals = tuple(
            self._signal_declaration(item, names=names, expressions=expressions)
            for item in (*module.signals, *module.variables)
        )

        label_allocator = VhdlNameAllocator(self._name_style)
        for name in names.values():
            label_allocator.reserve(name)
        items: list[VhdlItemIR] = []
        for position, item in enumerate(module.items, start=1):
            if isinstance(item, ContinuousAssignment):
                target = expressions.expression(item.target)
                items.append(
                    VhdlConcurrentAssignmentIR(
                        target=target,
                        value=expressions.assignment_value(
                            item.value,
                            item.target,
                            target_text=target,
                        ),
                        leading_comments=tuple(item.leading_comments),
                        trailing_comments=tuple(item.trailing_comments),
                    )
                )
            elif isinstance(item, CombinationalProcess):
                items.append(
                    self._lower_combinational_process(
                        item,
                        position=position,
                        expressions=expressions,
                        label_allocator=label_allocator,
                    )
                )
            elif isinstance(item, SequentialProcess):
                items.append(
                    self._lower_sequential_process(
                        item,
                        position=position,
                        expressions=expressions,
                        label_allocator=label_allocator,
                    )
                )
            elif isinstance(item, Instance):
                items.append(
                    self._lower_instance(
                        item,
                        position=position,
                        expressions=expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                    )
                )
            elif isinstance(item, ForGenerate):
                items.append(
                    self._lower_for_generate(
                        item,
                        path=item.label,
                        module_name=module.name,
                        expressions=expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                        mappings=mappings,
                    )
                )
            elif isinstance(item, IfGenerate):
                items.append(
                    self._lower_if_generate(
                        item,
                        path=item.label,
                        module_name=module.name,
                        expressions=expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                        mappings=mappings,
                    )
                )
            else:
                raise GenerationError(
                    f"{type(item).__name__} 尚未进入 v0.3 MVP target lowering",
                    code="HDLX-V2V-MVP-SLICE",
                    source_span=item.source_span,
                )

        return VhdlDesignUnitIR(
            entity_name=entity_name,
            architecture_name="rtl",
            generics=generics,
            ports=ports,
            signals=signals,
            items=tuple(items),
            leading_comments=tuple(module.leading_comments),
            trailing_comments=tuple(module.trailing_comments),
        )

    @staticmethod
    def _signal_declaration(
        declaration: object,
        *,
        names: dict[str, str],
        expressions: VhdlExpressionLowering,
    ) -> VhdlDeclarationIR:
        if declaration.initial_value is not None:
            raise GenerationError(
                f"declaration initializer for {declaration.name!r} 无法保持 time-zero 语义",
                code="HDLX-V2V-DECLARATION-INITIALIZER",
                source_span=declaration.source_span,
            )
        return VhdlDeclarationIR(
            name=names[declaration.name],
            type_text=expressions.type_text(declaration.rtl_type),
            leading_comments=tuple(declaration.leading_comments),
            trailing_comments=tuple(declaration.trailing_comments),
        )

    def _lower_combinational_process(
        self,
        process: CombinationalProcess,
        *,
        position: int,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
    ) -> VhdlProcessIR:
        label = label_allocator.allocate(process.label or f"comb_process_{position}")
        targets = self._statement_target_order(process.body)
        variable_allocator = VhdlNameAllocator(self._name_style)
        for name in expressions.names.values():
            variable_allocator.reserve(name)
        replacements: dict[str, str] = {}
        declarations: list[VhdlDeclarationIR] = []
        initialization: list[VhdlStatementIR] = []
        final_updates: list[VhdlStatementIR] = []
        for source_name in targets:
            rtl_type = expressions.rtl_types.get(source_name)
            if rtl_type is None:
                raise GenerationError(
                    f"combinational target {source_name!r} 缺少 declaration/type",
                    code="HDLX-V2V-UNDECLARED-TARGET",
                    source_span=process.source_span,
                )
            signal_name = expressions.names[source_name]
            variable_name = variable_allocator.allocate(f"{signal_name}_next")
            replacements[source_name] = variable_name
            declarations.append(
                VhdlDeclarationIR(
                    name=variable_name,
                    type_text=expressions.type_text(rtl_type),
                )
            )
            initialization.append(
                VhdlAssignmentIR(
                    target=variable_name,
                    operator=":=",
                    value=signal_name,
                )
            )
            final_updates.append(
                VhdlAssignmentIR(
                    target=signal_name,
                    operator="<=",
                    value=variable_name,
                )
            )

        body = self._lower_statements(
            process.body,
            process_kind="comb",
            expressions=expressions,
            replacements=replacements,
        )
        sensitivity = (
            ("all",)
            if not process.sensitivity
            else tuple(expressions.expression(item) for item in process.sensitivity)
        )
        return VhdlProcessIR(
            label=label,
            sensitivity=sensitivity,
            declarations=tuple(declarations),
            body=tuple((*initialization, *body, *final_updates)),
            leading_comments=tuple(process.leading_comments),
            trailing_comments=tuple(process.trailing_comments),
        )

    def _lower_sequential_process(
        self,
        process: SequentialProcess,
        *,
        position: int,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
    ) -> VhdlProcessIR:
        label = label_allocator.allocate(process.label or f"seq_process_{position}")
        clock = expressions.expression(process.clock)
        edge_name = "rising_edge" if process.edge is EdgeKind.POSITIVE else "falling_edge"
        edge_condition = f"{edge_name}({clock})"
        normal_body = self._lower_statements(
            process.body,
            process_kind="seq",
            expressions=expressions,
            replacements={},
        )
        sensitivity = [clock]
        if process.reset is None:
            body: tuple[VhdlStatementIR, ...] = (
                VhdlIfStatementIR(condition=edge_condition, then_body=normal_body),
            )
        else:
            reset_signal = expressions.expression(process.reset.signal)
            active = "1" if process.reset.active_level is ActiveLevel.HIGH else "0"
            reset_condition = f"{reset_signal} = '{active}'"
            reset_body = self._lower_statements(
                process.reset_body,
                process_kind="seq",
                expressions=expressions,
                replacements={},
            )
            reset_if = VhdlIfStatementIR(
                condition=reset_condition,
                then_body=reset_body,
                else_body=normal_body,
            )
            if process.reset.kind is ResetKind.ASYNCHRONOUS:
                sensitivity.append(reset_signal)
                body = (
                    VhdlIfStatementIR(
                        condition=reset_condition,
                        then_body=reset_body,
                        else_body=(
                            VhdlIfStatementIR(
                                condition=edge_condition,
                                then_body=normal_body,
                            ),
                        ),
                    ),
                )
            else:
                body = (
                    VhdlIfStatementIR(
                        condition=edge_condition,
                        then_body=(reset_if,),
                    ),
                )
        return VhdlProcessIR(
            label=label,
            sensitivity=tuple(dict.fromkeys(sensitivity)),
            declarations=(),
            body=body,
            leading_comments=tuple(process.leading_comments),
            trailing_comments=tuple(process.trailing_comments),
        )

    def _lower_statements(
        self,
        statements: Sequence[StatementNode],
        *,
        process_kind: str,
        expressions: VhdlExpressionLowering,
        replacements: dict[str, str],
    ) -> tuple[VhdlStatementIR, ...]:
        result: list[VhdlStatementIR] = []
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                expected = (
                    AssignmentKind.BLOCKING
                    if process_kind == "comb"
                    else AssignmentKind.NON_BLOCKING
                )
                if statement.assignment_kind is not expected:
                    code = (
                        "HDLX-V2V-COMBINATIONAL-NONBLOCKING"
                        if process_kind == "comb"
                        else "HDLX-V2V-SEQUENTIAL-BLOCKING"
                    )
                    raise GenerationError(
                        "procedural assignment operator 与 process 分类不一致",
                        code=code,
                        source_span=statement.source_span,
                    )
                target = expressions.expression(
                    statement.target,
                    replacements=replacements,
                )
                result.append(
                    VhdlAssignmentIR(
                        target=target,
                        operator=":=" if process_kind == "comb" else "<=",
                        value=expressions.assignment_value(
                            statement.value,
                            statement.target,
                            target_text=target,
                            replacements=replacements,
                        ),
                        leading_comments=tuple(statement.leading_comments),
                        trailing_comments=tuple(statement.trailing_comments),
                    )
                )
            elif isinstance(statement, IfStatement):
                result.append(
                    VhdlIfStatementIR(
                        condition=expressions.condition(
                            statement.condition,
                            replacements=replacements,
                        ),
                        then_body=self._lower_statements(
                            statement.then_body,
                            process_kind=process_kind,
                            expressions=expressions,
                            replacements=replacements,
                        ),
                        else_body=self._lower_statements(
                            statement.else_body,
                            process_kind=process_kind,
                            expressions=expressions,
                            replacements=replacements,
                        ),
                        leading_comments=tuple(statement.leading_comments),
                        trailing_comments=tuple(statement.trailing_comments),
                    )
                )
            elif isinstance(statement, CaseStatement):
                alternatives = tuple(
                    VhdlCaseAlternativeIR(
                        selectors=tuple(
                            expressions.expression(
                                selector,
                                replacements=replacements,
                            )
                            for selector in alternative.selectors
                        ),
                        body=self._lower_statements(
                            alternative.body,
                            process_kind=process_kind,
                            expressions=expressions,
                            replacements=replacements,
                        ),
                    )
                    for alternative in statement.alternatives
                )
                result.append(
                    VhdlCaseStatementIR(
                        expression=expressions.expression(
                            statement.expression,
                            replacements=replacements,
                        ),
                        alternatives=alternatives,
                        default_body=self._lower_statements(
                            statement.default_body,
                            process_kind=process_kind,
                            expressions=expressions,
                            replacements=replacements,
                        ),
                        leading_comments=tuple(statement.leading_comments),
                        trailing_comments=tuple(statement.trailing_comments),
                    )
                )
            elif isinstance(statement, BlockStatement):
                result.extend(
                    self._lower_statements(
                        statement.statements,
                        process_kind=process_kind,
                        expressions=expressions,
                        replacements=replacements,
                    )
                )
            elif isinstance(statement, NullStatement):
                result.append(
                    VhdlNullStatementIR(
                        leading_comments=tuple(statement.leading_comments),
                        trailing_comments=tuple(statement.trailing_comments),
                    )
                )
            elif isinstance(statement, ForStatement):
                raise GenerationError(
                    "procedural for loop 尚未进入 v0.3 MVP",
                    code="HDLX-V2V-FOR-STATEMENT",
                    source_span=statement.source_span,
                )
            else:
                raise GenerationError(
                    f"statement {type(statement).__name__} 不在 v0.3 MVP 内",
                    code="HDLX-V2V-STATEMENT",
                    source_span=statement.source_span,
                )
        return tuple(result)

    def _lower_for_generate(
        self,
        generate: ForGenerate,
        *,
        path: str,
        module_name: str,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
        modules: dict[str, Module],
        unit_names: dict[str, str],
        scope_names: dict[str, dict[str, str]],
        mappings: dict[str, str],
    ) -> VhdlForGenerateIR:
        label = label_allocator.allocate(generate.label)
        mappings[f"{module_name}.{path}"] = label
        index_allocator = VhdlNameAllocator(self._name_style)
        for name in expressions.names.values():
            index_allocator.reserve(name)
        index_name = index_allocator.allocate(generate.index_name)
        mappings[f"{module_name}.{path}.{generate.index_name}"] = index_name
        child_expressions = VhdlExpressionLowering(
            {**expressions.names, generate.index_name: index_name},
            dict(expressions.rtl_types),
        )
        declarations, items = self._lower_generate_scope(
            generate.body,
            path=path,
            module_name=module_name,
            expressions=child_expressions,
            label_allocator=label_allocator,
            modules=modules,
            unit_names=unit_names,
            scope_names=scope_names,
            mappings=mappings,
        )
        direction = "to" if generate.range.direction.value == "ascending" else "downto"
        return VhdlForGenerateIR(
            label=label,
            index_name=index_name,
            left=expressions.bound_text(generate.range.left),
            direction=direction,
            right=expressions.bound_text(generate.range.right),
            declarations=declarations,
            items=items,
            leading_comments=tuple(generate.leading_comments),
            trailing_comments=tuple(generate.trailing_comments),
        )

    def _lower_if_generate(
        self,
        generate: IfGenerate,
        *,
        path: str,
        module_name: str,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
        modules: dict[str, Module],
        unit_names: dict[str, str],
        scope_names: dict[str, dict[str, str]],
        mappings: dict[str, str],
    ) -> VhdlIfGenerateIR:
        label = label_allocator.allocate(generate.label)
        mappings[f"{module_name}.{path}"] = label
        then_declarations, then_items = self._lower_generate_scope(
            generate.then_body,
            path=path,
            module_name=module_name,
            expressions=expressions,
            label_allocator=label_allocator,
            modules=modules,
            unit_names=unit_names,
            scope_names=scope_names,
            mappings=mappings,
        )
        else_declarations, else_items = self._lower_generate_scope(
            generate.else_body,
            path=f"{path}.else",
            module_name=module_name,
            expressions=expressions,
            label_allocator=label_allocator,
            modules=modules,
            unit_names=unit_names,
            scope_names=scope_names,
            mappings=mappings,
        )
        return VhdlIfGenerateIR(
            label=label,
            condition=expressions.condition(generate.condition),
            then_declarations=then_declarations,
            then_items=then_items,
            else_declarations=else_declarations,
            else_items=else_items,
            leading_comments=tuple(generate.leading_comments),
            trailing_comments=tuple(generate.trailing_comments),
        )

    def _lower_generate_scope(
        self,
        source_items: Sequence[object],
        *,
        path: str,
        module_name: str,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
        modules: dict[str, Module],
        unit_names: dict[str, str],
        scope_names: dict[str, dict[str, str]],
        mappings: dict[str, str],
    ) -> tuple[tuple[VhdlDeclarationIR, ...], tuple[VhdlItemIR, ...]]:
        local_names = dict(expressions.names)
        local_types = dict(expressions.rtl_types)
        allocator = VhdlNameAllocator(self._name_style)
        for name in local_names.values():
            allocator.reserve(name)
        declaration_nodes = [
            item for item in source_items if isinstance(item, Signal | Variable)
        ]
        for declaration in declaration_nodes:
            target_name = allocator.allocate(declaration.name)
            local_names[declaration.name] = target_name
            local_types[declaration.name] = declaration.rtl_type
            mappings[f"{module_name}.{path}.{declaration.name}"] = target_name
        local_expressions = VhdlExpressionLowering(local_names, local_types)
        declarations = tuple(
            self._signal_declaration(
                declaration,
                names=local_names,
                expressions=local_expressions,
            )
            for declaration in declaration_nodes
        )
        items: list[VhdlItemIR] = []
        for position, item in enumerate(source_items, start=1):
            if isinstance(item, Signal | Variable):
                continue
            if isinstance(item, ContinuousAssignment):
                target = local_expressions.expression(item.target)
                items.append(
                    VhdlConcurrentAssignmentIR(
                        target=target,
                        value=local_expressions.assignment_value(
                            item.value,
                            item.target,
                            target_text=target,
                        ),
                        leading_comments=tuple(item.leading_comments),
                        trailing_comments=tuple(item.trailing_comments),
                    )
                )
            elif isinstance(item, CombinationalProcess):
                items.append(
                    self._lower_combinational_process(
                        item,
                        position=position,
                        expressions=local_expressions,
                        label_allocator=label_allocator,
                    )
                )
            elif isinstance(item, SequentialProcess):
                items.append(
                    self._lower_sequential_process(
                        item,
                        position=position,
                        expressions=local_expressions,
                        label_allocator=label_allocator,
                    )
                )
            elif isinstance(item, Instance):
                items.append(
                    self._lower_instance(
                        item,
                        position=position,
                        expressions=local_expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                    )
                )
            elif isinstance(item, ForGenerate):
                items.append(
                    self._lower_for_generate(
                        item,
                        path=f"{path}.{item.label}",
                        module_name=module_name,
                        expressions=local_expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                        mappings=mappings,
                    )
                )
            elif isinstance(item, IfGenerate):
                items.append(
                    self._lower_if_generate(
                        item,
                        path=f"{path}.{item.label}",
                        module_name=module_name,
                        expressions=local_expressions,
                        label_allocator=label_allocator,
                        modules=modules,
                        unit_names=unit_names,
                        scope_names=scope_names,
                        mappings=mappings,
                    )
                )
            else:
                raise GenerationError(
                    f"generate body item {type(item).__name__} 不在 v0.3 MVP 内",
                    code="HDLX-V2V-GENERATE-MEMBER",
                    source_span=getattr(item, "source_span", None),
                )
        return declarations, tuple(items)

    def _lower_instance(
        self,
        instance: Instance,
        *,
        position: int,
        expressions: VhdlExpressionLowering,
        label_allocator: VhdlNameAllocator,
        modules: dict[str, Module],
        unit_names: dict[str, str],
        scope_names: dict[str, dict[str, str]],
    ) -> VhdlInstanceIR:
        referenced = modules.get(instance.referenced_unit)
        if referenced is None:
            raise GenerationError(
                f"instance {instance.name!r} 引用未包含的 unit {instance.referenced_unit!r}",
                code="HDLX-V2V-INSTANCE-UNIT",
                source_span=instance.source_span,
            )
        referenced_names = scope_names[referenced.name]
        generic_map = tuple(
            VhdlAssociationIR(
                formal=(
                    None
                    if binding.formal is None
                    else self._formal_name(binding.formal, referenced_names, binding)
                ),
                value=expressions.expression(binding.value),
            )
            for binding in instance.parameter_bindings
        )
        port_map = tuple(
            VhdlAssociationIR(
                formal=(
                    None
                    if binding.formal is None
                    else self._formal_name(binding.formal, referenced_names, binding)
                ),
                value=(
                    "open"
                    if binding.value is None
                    else expressions.expression(binding.value)
                ),
            )
            for binding in instance.port_bindings
        )
        return VhdlInstanceIR(
            label=label_allocator.allocate(instance.name or f"instance_{position}"),
            entity_name=unit_names[referenced.name],
            generic_map=generic_map,
            port_map=port_map,
            leading_comments=tuple(instance.leading_comments),
            trailing_comments=tuple(instance.trailing_comments),
        )

    @staticmethod
    def _formal_name(formal: str, names: dict[str, str], binding: object) -> str:
        target = names.get(formal)
        if target is None:
            raise GenerationError(
                f"association formal {formal!r} 不存在于 referenced unit",
                code="HDLX-V2V-ASSOCIATION-FORMAL",
                source_span=getattr(binding, "source_span", None),
            )
        return target

    @classmethod
    def _statement_target_order(cls, statements: Iterable[object]) -> list[str]:
        result: list[str] = []
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                name = VhdlExpressionLowering.root_name(statement.target)
                if name is not None and name not in result:
                    result.append(name)
            elif isinstance(statement, IfStatement):
                for name in cls._statement_target_order(
                    (*statement.then_body, *statement.else_body)
                ):
                    if name not in result:
                        result.append(name)
            elif isinstance(statement, CaseStatement):
                nested = [
                    item
                    for alternative in statement.alternatives
                    for item in alternative.body
                ]
                nested.extend(statement.default_body)
                for name in cls._statement_target_order(nested):
                    if name not in result:
                        result.append(name)
            elif isinstance(statement, BlockStatement):
                for name in cls._statement_target_order(statement.statements):
                    if name not in result:
                        result.append(name)
        return result


__all__ = ["VhdlLowering"]
