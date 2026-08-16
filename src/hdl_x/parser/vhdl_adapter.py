"""VHDL frontend 私有 Raw 表示到 canonical RTL IR 的适配器。"""

from __future__ import annotations

from collections.abc import Mapping

from hdl_x.diagnostics import SemanticError, UnsupportedConstructError
from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    BooleanType,
    CaseAlternative,
    CaseStatement,
    CombinationalProcess,
    Concatenation,
    ContinuousAssignment,
    Design,
    EdgeKind,
    ForGenerate,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Instance,
    IntegerType,
    Literal,
    LiteralKind,
    Module,
    NullStatement,
    Parameter,
    ParameterBinding,
    Port,
    PortBinding,
    PortDirection,
    ProceduralAssignment,
    RangeDirection,
    ResetKind,
    ResetSpec,
    RTLType,
    ScalarType,
    SequentialProcess,
    Signal,
    SourceLocation,
    SourceSpan,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    VectorRange,
    VectorType,
)
from hdl_x.parser.base import ParserAdapter
from hdl_x.parser.ghdl.raw import (
    RawActiveLevel,
    RawArchitecture,
    RawAssociation,
    RawBinaryExpression,
    RawBinaryOperator,
    RawCaseStatement,
    RawCombinationalProcess,
    RawComponentDeclaration,
    RawConcurrentAssignment,
    RawConditionalExpression,
    RawDesign,
    RawEdgeKind,
    RawEntity,
    RawExpression,
    RawForGenerate,
    RawIdentifier,
    RawIfGenerate,
    RawIfStatement,
    RawIndexExpression,
    RawInstance,
    RawInstantiationKind,
    RawLiteral,
    RawLiteralKind,
    RawNullStatement,
    RawParameter,
    RawPort,
    RawPortDirection,
    RawProceduralAssignment,
    RawRange,
    RawRangeDirection,
    RawResetKind,
    RawSequentialProcess,
    RawSignal,
    RawSourceLocation,
    RawType,
    RawTypeKind,
    RawUnaryExpression,
    RawUnaryOperator,
)


class VhdlAdapter(ParserAdapter[RawDesign]):
    """将 GHDL 隔离层的纯 Python 数据转换为语言中立 IR。"""

    def adapt(self, representation: RawDesign) -> Design:
        architectures: dict[str, list[RawArchitecture]] = {}
        for architecture in representation.architectures:
            architectures.setdefault(architecture.entity_name.casefold(), []).append(architecture)

        entities_by_name: dict[str, RawEntity] = {}
        for entity in representation.entities:
            normalized_name = entity.name.casefold()
            if normalized_name in entities_by_name:
                self._raise_semantic(
                    entity.source,
                    f"VHDL entity 名称 {entity.name!r} 按大小写不敏感规则发生冲突。",
                    "HDLX-VHDL-DUPLICATE-ENTITY",
                )
            entities_by_name[normalized_name] = entity

        for architecture in representation.architectures:
            if architecture.entity_name.casefold() not in entities_by_name:
                self._raise_semantic(
                    architecture.source,
                    f"architecture {architecture.name!r} 引用未提供的 entity "
                    f"{architecture.entity_name!r}。",
                    "HDLX-VHDL-ARCHITECTURE-UNKNOWN-ENTITY",
                )

        modules: list[Module] = []
        for entity in representation.entities:
            normalized_name = entity.name.casefold()
            matching_architectures = architectures.get(normalized_name, [])
            if not matching_architectures:
                self._raise_semantic(
                    entity.source,
                    f"entity {entity.name!r} 缺少可转换的 architecture；"
                    "当前 MVP 不提供隐式 black-box 模式。",
                    "HDLX-VHDL-ARCHITECTURE-MISSING",
                )
            if len(matching_architectures) > 1:
                self._raise_semantic(
                    entity.source,
                    f"entity {entity.name!r} 存在多个 architecture，当前转换未指定选择项。",
                    "HDLX-VHDL-ARCHITECTURE-AMBIGUOUS",
                )
            architecture = matching_architectures[0]
            modules.append(self._adapt_module(entity, architecture, entities_by_name))

        if not modules:
            raise SemanticError(
                "VHDL RawDesign 不含可转换 entity。",
                code="HDLX-VHDL-NO-ENTITY",
                file=str(representation.source_path),
            )
        return Design(
            name=representation.source_path.stem,
            modules=modules,
            top=modules[0].name if len(modules) == 1 else None,
        )

    def _adapt_module(
        self,
        entity: RawEntity,
        architecture: RawArchitecture | None,
        entities_by_name: Mapping[str, RawEntity],
    ) -> Module:
        symbol_types: dict[str, RawType] = {}
        architecture_signals = () if architecture is None else architecture.signals
        for declaration in (*entity.parameters, *entity.ports, *architecture_signals):
            normalized_name = declaration.name.casefold()
            if normalized_name in symbol_types:
                self._raise_semantic(
                    declaration.source,
                    f"entity {entity.name!r} 中声明 {declaration.name!r} 按 VHDL "
                    "大小写不敏感规则发生冲突。",
                    "HDLX-VHDL-DUPLICATE-DECLARATION",
                )
            symbol_types[normalized_name] = declaration.type

        parameters = [
            Parameter(
                name=parameter.name,
                rtl_type=self._adapt_type(parameter.type, symbol_types),
                default=(
                    None
                    if parameter.default is None
                    else self._adapt_expression(parameter.default, symbol_types)
                ),
                source_span=self._span(parameter.source),
            )
            for parameter in entity.parameters
        ]
        direction_map = {
            RawPortDirection.IN: PortDirection.INPUT,
            RawPortDirection.OUT: PortDirection.OUTPUT,
            RawPortDirection.INOUT: PortDirection.INOUT,
        }
        ports: list[Port] = []
        for port in entity.ports:
            if port.type.kind is RawTypeKind.INTEGER:
                self._raise_semantic(
                    port.source,
                    f"端口 {port.name!r} 使用 integer-like 类型；当前 MVP 仅支持"
                    " integer-like generic，不能安全生成 Verilog-2001 integer port。",
                    "HDLX-VHDL-PORT-TYPE",
                )
            ports.append(
                Port(
                    name=port.name,
                    direction=direction_map[port.direction],
                    rtl_type=self._adapt_type(port.type, symbol_types),
                    source_span=self._span(port.source),
                )
            )
        signals = [
            Signal(
                name=signal.name,
                rtl_type=self._adapt_type(signal.type, symbol_types),
                source_span=self._span(signal.source),
            )
            for signal in architecture_signals
        ]
        items = (
            []
            if architecture is None
            else [
                self._adapt_item(item, symbol_types, entities_by_name)
                for item in architecture.items
            ]
        )
        return Module(
            name=entity.name,
            parameters=parameters,
            ports=ports,
            signals=signals,
            items=items,
            source_span=self._span(entity.source),
        )

    def _adapt_item(
        self,
        item: RawConcurrentAssignment
        | RawCombinationalProcess
        | RawSequentialProcess
        | RawInstance
        | RawSignal
        | RawForGenerate
        | RawIfGenerate,
        symbol_types: Mapping[str, RawType],
        entities_by_name: Mapping[str, RawEntity],
    ) -> (
        ContinuousAssignment
        | CombinationalProcess
        | SequentialProcess
        | Instance
        | Signal
        | ForGenerate
        | IfGenerate
    ):
        if isinstance(item, RawSignal):
            return Signal(
                name=item.name,
                rtl_type=self._adapt_type(item.type, symbol_types),
                source_span=self._span(item.source),
            )
        if isinstance(item, RawConcurrentAssignment):
            return ContinuousAssignment(
                target=self._adapt_expression(item.target, symbol_types),
                value=self._adapt_assignment_value(item.target, item.value, symbol_types),
                source_span=self._span(item.source),
            )
        if isinstance(item, RawCombinationalProcess):
            self._validate_combinational_signal_dependencies(item)
            return CombinationalProcess(
                label=item.label,
                sensitivity=[
                    self._adapt_expression(expression, symbol_types)
                    for expression in item.sensitivity
                ],
                body=[self._adapt_statement(statement, symbol_types) for statement in item.body],
                source_span=self._span(item.source),
            )
        if isinstance(item, RawSequentialProcess):
            edge_map = {
                RawEdgeKind.POSITIVE: EdgeKind.POSITIVE,
                RawEdgeKind.NEGATIVE: EdgeKind.NEGATIVE,
            }
            reset = None
            if item.reset is not None:
                reset = ResetSpec(
                    signal=self._adapt_expression(item.reset.signal, symbol_types),
                    kind={
                        RawResetKind.SYNCHRONOUS: ResetKind.SYNCHRONOUS,
                        RawResetKind.ASYNCHRONOUS: ResetKind.ASYNCHRONOUS,
                    }[item.reset.kind],
                    active_level={
                        RawActiveLevel.HIGH: ActiveLevel.HIGH,
                        RawActiveLevel.LOW: ActiveLevel.LOW,
                    }[item.reset.active_level],
                    source_span=self._span(item.reset.source),
                )
            return SequentialProcess(
                label=item.label,
                clock=self._adapt_expression(item.clock, symbol_types),
                edge=edge_map[item.edge],
                reset=reset,
                reset_body=[
                    self._adapt_statement(
                        statement,
                        symbol_types,
                        assignment_kind=AssignmentKind.NON_BLOCKING,
                    )
                    for statement in item.reset_body
                ],
                body=[
                    self._adapt_statement(
                        statement,
                        symbol_types,
                        assignment_kind=AssignmentKind.NON_BLOCKING,
                    )
                    for statement in item.body
                ],
                source_span=self._span(item.source),
            )
        if isinstance(item, RawInstance):
            return self._adapt_instance(item, symbol_types, entities_by_name)
        if isinstance(item, RawForGenerate):
            range_direction = (
                RangeDirection.ASCENDING
                if item.range.direction is RawRangeDirection.TO
                else RangeDirection.DESCENDING
            )
            body_symbols = dict(symbol_types)
            index_key = item.index_name.casefold()
            body_symbols[index_key] = RawType(
                kind=RawTypeKind.INTEGER,
                source_name="integer",
                source=item.source,
            )
            return ForGenerate(
                label=item.label,
                index_name=item.index_name,
                range=VectorRange(
                    left=self._adapt_expression(item.range.left, symbol_types),
                    right=self._adapt_expression(item.range.right, symbol_types),
                    direction=range_direction,
                    source_span=self._span(item.range.source),
                ),
                body=self._adapt_generate_body(
                    item.body,
                    body_symbols,
                    entities_by_name,
                    protected_names={index_key},
                ),
                source_span=self._span(item.source),
            )
        if isinstance(item, RawIfGenerate):
            return IfGenerate(
                label=item.label,
                condition=self._adapt_expression(item.condition, symbol_types),
                then_body=self._adapt_generate_body(item.then_body, symbol_types, entities_by_name),
                else_body=self._adapt_generate_body(item.else_body, symbol_types, entities_by_name),
                source_span=self._span(item.source),
            )
        raise UnsupportedConstructError(
            f"Raw architecture item {type(item).__name__} 尚无 canonical 映射。",
            code="HDLX-VHDL-RAW-ITEM",
        )

    def _validate_combinational_signal_dependencies(self, process: RawCombinationalProcess) -> None:
        """拒绝 blocking assignment 无法保持的 VHDL delta-cycle 信号依赖。"""

        written: set[str] = set()
        read: set[str] = set()
        for statement in process.body:
            self._collect_statement_signal_accesses(statement, written, read)

        dependencies = sorted(written & read)
        if dependencies:
            names = ", ".join(repr(name) for name in dependencies)
            self._raise_semantic(
                process.source,
                "组合 process 同时写入并读取信号 "
                f"{names}；VHDL signal assignment 在 process 暂停后更新，"
                "不能安全降为 Verilog blocking assignment。",
                "HDLX-VHDL-PROCESS-SIGNAL-DEPENDENCY",
            )

    def _collect_statement_signal_accesses(
        self,
        statement: RawProceduralAssignment | RawIfStatement | RawCaseStatement | RawNullStatement,
        written: set[str],
        read: set[str],
    ) -> None:
        """递归收集组合 process 语句中的信号写入与读取。"""

        if isinstance(statement, RawProceduralAssignment):
            self._collect_target_signal_accesses(statement.target, written, read)
            self._collect_expression_reads(statement.value, read)
            return
        if isinstance(statement, RawIfStatement):
            self._collect_expression_reads(statement.condition, read)
            for nested in (*statement.then_body, *statement.else_body):
                self._collect_statement_signal_accesses(nested, written, read)
            return
        if isinstance(statement, RawCaseStatement):
            self._collect_expression_reads(statement.expression, read)
            for alternative in statement.alternatives:
                for selector in alternative.selectors:
                    self._collect_expression_reads(selector, read)
                for nested in alternative.body:
                    self._collect_statement_signal_accesses(nested, written, read)
            for nested in statement.default_body:
                self._collect_statement_signal_accesses(nested, written, read)

    def _collect_target_signal_accesses(
        self,
        target: RawExpression,
        written: set[str],
        read: set[str],
    ) -> None:
        """目标基底是写入；packed index 本身仍会在赋值时求值。"""

        if isinstance(target, RawIdentifier):
            written.add(target.name.casefold())
            return
        if isinstance(target, RawIndexExpression):
            self._collect_target_signal_accesses(target.value, written, read)
            self._collect_expression_reads(target.index, read)
            return
        self._collect_expression_reads(target, read)

    def _collect_expression_reads(self, expression: RawExpression, read: set[str]) -> None:
        """递归收集表达式中的名称读取，保持 VHDL 大小写不敏感语义。"""

        if isinstance(expression, RawIdentifier):
            read.add(expression.name.casefold())
            return
        if isinstance(expression, RawLiteral):
            return
        if isinstance(expression, RawUnaryExpression):
            self._collect_expression_reads(expression.operand, read)
            return
        if isinstance(expression, RawBinaryExpression):
            self._collect_expression_reads(expression.left, read)
            self._collect_expression_reads(expression.right, read)
            return
        if isinstance(expression, RawIndexExpression):
            self._collect_expression_reads(expression.value, read)
            self._collect_expression_reads(expression.index, read)
            return
        if isinstance(expression, RawConditionalExpression):
            self._collect_expression_reads(expression.condition, read)
            self._collect_expression_reads(expression.when_true, read)
            self._collect_expression_reads(expression.when_false, read)

    def _adapt_generate_body(
        self,
        items: tuple[
            RawSignal
            | RawConcurrentAssignment
            | RawCombinationalProcess
            | RawSequentialProcess
            | RawInstance
            | RawForGenerate
            | RawIfGenerate,
            ...,
        ],
        symbol_types: Mapping[str, RawType],
        entities_by_name: Mapping[str, RawEntity],
        *,
        protected_names: set[str] | None = None,
    ) -> list[
        Signal
        | ContinuousAssignment
        | CombinationalProcess
        | SequentialProcess
        | Instance
        | ForGenerate
        | IfGenerate
    ]:
        local_symbols = dict(symbol_types)
        local_names = set() if protected_names is None else set(protected_names)
        for item in items:
            if not isinstance(item, RawSignal):
                continue
            normalized_name = item.name.casefold()
            if normalized_name in local_names:
                self._raise_semantic(
                    item.source,
                    f"generate 作用域中的声明 {item.name!r} 按 VHDL 大小写不敏感规则发生冲突。",
                    "HDLX-VHDL-DUPLICATE-GENERATE-DECLARATION",
                )
            local_names.add(normalized_name)
            local_symbols[normalized_name] = item.type
        return [self._adapt_item(item, local_symbols, entities_by_name) for item in items]

    def _adapt_instance(
        self,
        instance: RawInstance,
        symbol_types: Mapping[str, RawType],
        entities_by_name: Mapping[str, RawEntity],
    ) -> Instance:
        referenced = entities_by_name.get(instance.referenced_unit.casefold())
        if referenced is None:
            self._raise_semantic(
                instance.source,
                f"实例 {instance.name!r} 引用未知单元 "
                f"{instance.referenced_unit!r}；当前 MVP 无法证明其接口方向。",
                "HDLX-VHDL-INSTANCE-UNKNOWN-UNIT",
            )
        if instance.instantiation_kind is RawInstantiationKind.COMPONENT:
            component = instance.component_declaration
            if component is None:
                self._raise_semantic(
                    instance.source,
                    f"component instance {instance.name!r} 缺少声明接口，无法证明默认绑定语义。",
                    "HDLX-VHDL-COMPONENT-BINDING",
                )
            self._validate_component_binding(instance, component, referenced)
        elif instance.component_declaration is not None:
            self._raise_semantic(
                instance.source,
                f"direct entity instance {instance.name!r} 携带了矛盾的 component 声明。",
                "HDLX-VHDL-INSTANCE-KIND",
            )
        referenced_unit = referenced.name
        parameter_bindings = self._adapt_associations(
            instance.parameter_associations,
            () if referenced is None else referenced.parameters,
            referenced_known=referenced is not None,
            instance=instance,
            role="parameter",
            symbol_types=symbol_types,
        )
        port_bindings = self._adapt_associations(
            instance.port_associations,
            () if referenced is None else referenced.ports,
            referenced_known=referenced is not None,
            instance=instance,
            role="port",
            symbol_types=symbol_types,
        )
        self._validate_instance_port_widths(instance, referenced, symbol_types)
        return Instance(
            referenced_unit=referenced_unit,
            name=instance.name,
            parameter_bindings=parameter_bindings,
            port_bindings=port_bindings,
            source_span=self._span(instance.source),
        )

    def _validate_component_binding(
        self,
        instance: RawInstance,
        component: RawComponentDeclaration,
        entity: RawEntity,
    ) -> None:
        """仅在 component 与同文件 entity 接口可逐项证明等价时绑定。"""

        if component.name.casefold() != instance.referenced_unit.casefold():
            self._raise_component_binding(
                instance,
                "实例引用名与其词法作用域中的 component 声明名称不一致",
            )
        if component.name.casefold() != entity.name.casefold():
            self._raise_component_binding(
                instance,
                f"component {component.name!r} 无同名 entity 接口",
            )

        self._validate_component_parameters(instance, component.parameters, entity.parameters)
        self._validate_component_ports(instance, component.ports, entity.ports)

    def _validate_component_parameters(
        self,
        instance: RawInstance,
        component_parameters: tuple[RawParameter, ...],
        entity_parameters: tuple[RawParameter, ...],
    ) -> None:
        if len(component_parameters) != len(entity_parameters):
            self._raise_component_binding(
                instance,
                "component 与 entity 的 generic 数量不一致",
            )
        for index, (component_item, entity_item) in enumerate(
            zip(component_parameters, entity_parameters, strict=True)
        ):
            if component_item.name.casefold() != entity_item.name.casefold():
                self._raise_component_binding(
                    instance,
                    f"generic #{index} 名称 {component_item.name!r} 与 {entity_item.name!r} 不一致",
                )
            if self._raw_type_signature(component_item.type) != self._raw_type_signature(
                entity_item.type
            ):
                self._raise_component_binding(
                    instance,
                    f"generic {component_item.name!r} 类型不一致",
                )
            if self._raw_default_signature(component_item.default) != self._raw_default_signature(
                entity_item.default
            ):
                self._raise_component_binding(
                    instance,
                    f"generic {component_item.name!r} 默认值不一致",
                )

    def _validate_component_ports(
        self,
        instance: RawInstance,
        component_ports: tuple[RawPort, ...],
        entity_ports: tuple[RawPort, ...],
    ) -> None:
        if len(component_ports) != len(entity_ports):
            self._raise_component_binding(
                instance,
                "component 与 entity 的 port 数量不一致",
            )
        for index, (component_item, entity_item) in enumerate(
            zip(component_ports, entity_ports, strict=True)
        ):
            if component_item.name.casefold() != entity_item.name.casefold():
                self._raise_component_binding(
                    instance,
                    f"port #{index} 名称 {component_item.name!r} 与 {entity_item.name!r} 不一致",
                )
            if component_item.direction is not entity_item.direction:
                self._raise_component_binding(
                    instance,
                    f"port {component_item.name!r} 方向不一致",
                )
            if self._raw_type_signature(component_item.type) != self._raw_type_signature(
                entity_item.type
            ):
                self._raise_component_binding(
                    instance,
                    f"port {component_item.name!r} 类型不一致",
                )
            if self._raw_default_signature(component_item.default) != self._raw_default_signature(
                entity_item.default
            ):
                self._raise_component_binding(
                    instance,
                    f"port {component_item.name!r} 默认值不一致",
                )

    def _raise_component_binding(self, instance: RawInstance, detail: str) -> None:
        self._raise_semantic(
            instance.source,
            f"实例 {instance.name!r} 的 component 默认绑定不能安全转换：{detail}。",
            "HDLX-VHDL-COMPONENT-BINDING",
        )

    def _validate_instance_port_widths(
        self,
        instance: RawInstance,
        entity: RawEntity,
        symbol_types: Mapping[str, RawType],
    ) -> None:
        """在 generic 实参替换后证明每个已连接向量端口等宽。"""

        generic_bindings = self._instance_generic_binding_signatures(instance, entity)
        ports_by_name = {port.name.casefold(): port for port in entity.ports}
        for association in instance.port_associations:
            if association.value is None:
                continue
            if association.formal is not None:
                formal = ports_by_name[association.formal.casefold()]
            else:
                assert association.position is not None
                formal = entity.ports[association.position]

            actual_width = self._vector_width_signature(association.value, symbol_types)
            if formal.type.kind is not RawTypeKind.VECTOR:
                if actual_width is not None:
                    self._raise_instance_port_width(instance, association, formal.name)
                continue
            if formal.type.range is None:
                self._raise_instance_port_width(instance, association, formal.name)
            formal_width = self._bound_range_width_signature(
                formal.type.range,
                generic_bindings,
            )
            if actual_width is None or actual_width != formal_width:
                self._raise_instance_port_width(instance, association, formal.name)

    def _instance_generic_binding_signatures(
        self,
        instance: RawInstance,
        entity: RawEntity,
    ) -> dict[str, tuple[object, ...]]:
        """将 child generic 解析为调用方作用域中的表达式签名。"""

        overrides: dict[str, RawExpression] = {}
        parameters_by_name = {item.name.casefold(): item for item in entity.parameters}
        for association in instance.parameter_associations:
            if association.value is None:
                continue
            if association.formal is not None:
                key = association.formal.casefold()
                assert key in parameters_by_name
            else:
                assert association.position is not None
                key = entity.parameters[association.position].name.casefold()
            # generic actual 位于调用方作用域；即使同名，也不能再次按 child
            # generic 递归替换。
            overrides[key] = association.value

        bindings: dict[str, tuple[object, ...]] = {}
        for parameter in entity.parameters:
            key = parameter.name.casefold()
            if key in overrides:
                bindings[key] = self._raw_expression_signature(overrides[key])
            elif parameter.default is not None:
                bindings[key] = self._bound_raw_expression_signature(
                    parameter.default,
                    bindings,
                )
            else:
                bindings[key] = ("unbound_generic", key)
        return bindings

    def _raise_instance_port_width(
        self,
        instance: RawInstance,
        association: RawAssociation,
        formal_name: str,
    ) -> None:
        self._raise_semantic(
            association.source or instance.source,
            f"实例 {instance.name!r} 的端口 {formal_name!r} 无法证明 formal/actual "
            "向量宽度在所有合法 generic 取值下等价。",
            "HDLX-VHDL-INSTANCE-PORT-WIDTH",
        )

    def _adapt_associations(
        self,
        associations: tuple[RawAssociation, ...],
        interface: tuple[RawParameter, ...] | tuple[RawPort, ...],
        *,
        referenced_known: bool,
        instance: RawInstance,
        role: str,
        symbol_types: Mapping[str, RawType],
    ) -> list[ParameterBinding] | list[PortBinding]:
        has_named = any(item.formal is not None for item in associations)
        has_positional = any(item.position is not None for item in associations)
        interface_by_name = {item.name.casefold(): item for item in interface}
        result: list[ParameterBinding | PortBinding] = []
        selectors: set[str | int] = set()

        for association in associations:
            formal = association.formal
            position = association.position
            if position is not None:
                if not referenced_known:
                    self._raise_semantic(
                        association.source or instance.source,
                        f"实例 {instance.name!r} 对未知单元 {instance.referenced_unit!r} "
                        f"使用 positional {role} map，无法安全解析接口顺序。",
                        "HDLX-VHDL-INSTANCE-POSITIONAL-UNKNOWN",
                    )
                if position >= len(interface):
                    self._raise_semantic(
                        association.source or instance.source,
                        f"实例 {instance.name!r} 的 {role} map 位置 {position} 超出 "
                        f"{instance.referenced_unit!r} 接口范围。",
                        f"HDLX-VHDL-INSTANCE-{role.upper()}-RANGE",
                    )
                if has_named:
                    formal = interface[position].name
                    position = None
            elif formal is not None and referenced_known:
                declared = interface_by_name.get(formal.casefold())
                if declared is None:
                    self._raise_semantic(
                        association.source or instance.source,
                        f"实例 {instance.name!r} 关联未知 {role} {formal!r}。",
                        f"HDLX-VHDL-INSTANCE-UNKNOWN-{role.upper()}",
                    )
                formal = declared.name

            selector: str | int
            if formal is not None:
                selector = formal.casefold()
            else:
                assert position is not None
                selector = position
            if selector in selectors:
                self._raise_semantic(
                    association.source or instance.source,
                    f"实例 {instance.name!r} 重复关联 {role} {selector!r}。",
                    f"HDLX-VHDL-INSTANCE-DUPLICATE-{role.upper()}",
                )
            selectors.add(selector)

            value = (
                None
                if association.value is None
                else self._adapt_expression(association.value, symbol_types)
            )
            source_span = self._span(association.source)
            if role == "parameter":
                if value is None:
                    self._raise_semantic(
                        association.source or instance.source,
                        f"实例 {instance.name!r} 的 parameter association 不能为 open。",
                        "HDLX-VHDL-INSTANCE-PARAMETER-OPEN",
                    )
                result.append(
                    ParameterBinding(
                        formal=formal,
                        position=position,
                        value=value,
                        source_span=source_span,
                    )
                )
            else:
                result.append(
                    PortBinding(
                        formal=formal,
                        position=position,
                        value=value,
                        source_span=source_span,
                    )
                )

        if has_named and has_positional and not referenced_known:
            self._raise_semantic(
                instance.source,
                f"实例 {instance.name!r} 的混合 {role} map 无法安全解析。",
                "HDLX-VHDL-INSTANCE-MIXED-ASSOCIATION",
            )
        return result

    def _adapt_statement(
        self,
        statement: RawProceduralAssignment | RawIfStatement | RawCaseStatement | RawNullStatement,
        symbol_types: Mapping[str, RawType],
        *,
        assignment_kind: AssignmentKind = AssignmentKind.BLOCKING,
    ) -> ProceduralAssignment | IfStatement | CaseStatement | NullStatement:
        if isinstance(statement, RawProceduralAssignment):
            return ProceduralAssignment(
                target=self._adapt_expression(statement.target, symbol_types),
                value=self._adapt_assignment_value(statement.target, statement.value, symbol_types),
                assignment_kind=assignment_kind,
                source_span=self._span(statement.source),
            )
        if isinstance(statement, RawIfStatement):
            return IfStatement(
                condition=self._adapt_expression(statement.condition, symbol_types),
                then_body=[
                    self._adapt_statement(item, symbol_types, assignment_kind=assignment_kind)
                    for item in statement.then_body
                ],
                else_body=[
                    self._adapt_statement(item, symbol_types, assignment_kind=assignment_kind)
                    for item in statement.else_body
                ],
                source_span=self._span(statement.source),
            )
        if isinstance(statement, RawCaseStatement):
            return CaseStatement(
                expression=self._adapt_expression(statement.expression, symbol_types),
                alternatives=[
                    CaseAlternative(
                        selectors=[
                            self._adapt_expression(selector, symbol_types)
                            for selector in alternative.selectors
                        ],
                        body=[
                            self._adapt_statement(
                                item,
                                symbol_types,
                                assignment_kind=assignment_kind,
                            )
                            for item in alternative.body
                        ],
                        source_span=self._span(alternative.source),
                    )
                    for alternative in statement.alternatives
                ],
                default_body=[
                    self._adapt_statement(item, symbol_types, assignment_kind=assignment_kind)
                    for item in statement.default_body
                ],
                source_span=self._span(statement.source),
            )
        if isinstance(statement, RawNullStatement):
            return NullStatement(source_span=self._span(statement.source))
        raise UnsupportedConstructError(
            f"Raw statement {type(statement).__name__} 尚无 canonical 映射。",
            code="HDLX-VHDL-RAW-STATEMENT",
        )

    def _adapt_type(self, raw_type: RawType, symbol_types: Mapping[str, RawType]) -> RTLType:
        source_span = self._span(raw_type.source)
        if raw_type.kind is RawTypeKind.SCALAR:
            return ScalarType(
                signed=raw_type.signed,
                four_state=raw_type.four_state,
                source_span=source_span,
            )
        if raw_type.kind is RawTypeKind.INTEGER:
            return IntegerType(source_span=source_span)
        if raw_type.kind is RawTypeKind.BOOLEAN:
            return BooleanType(source_span=source_span)
        if raw_type.kind is RawTypeKind.VECTOR:
            if raw_type.range is None:
                self._raise_semantic(
                    raw_type.source,
                    f"向量类型 {raw_type.source_name!r} 缺少离散范围。",
                    "HDLX-VHDL-VECTOR-RANGE",
                )
            if not self._range_is_provably_non_null(raw_type.range, symbol_types):
                self._raise_semantic(
                    raw_type.source,
                    "VHDL array range may be null, but Verilog packed ranges always "
                    "declare at least one bit; non-empty width must be provable for "
                    "all legal generic values.",
                    "HDLX-VHDL-NULL-VECTOR-RANGE",
                )
            direction = (
                RangeDirection.ASCENDING
                if raw_type.range.direction is RawRangeDirection.TO
                else RangeDirection.DESCENDING
            )
            return VectorType(
                range=VectorRange(
                    left=self._adapt_expression(raw_type.range.left, symbol_types),
                    right=self._adapt_expression(raw_type.range.right, symbol_types),
                    direction=direction,
                    source_span=self._span(raw_type.range.source),
                ),
                signed=raw_type.signed,
                four_state=raw_type.four_state,
                source_span=source_span,
            )
        self._raise_semantic(
            raw_type.source,
            f"Raw VHDL 类型 {raw_type.kind!r} 无 canonical 映射。",
            "HDLX-VHDL-RAW-TYPE",
        )

    def _adapt_expression(
        self,
        expression: RawExpression,
        symbol_types: Mapping[str, RawType],
        *,
        allow_root_mixed_arithmetic: bool = False,
    ) -> Identifier | Literal | UnaryExpr | BinaryExpr | TernaryExpr | Concatenation | Index:
        source_span = self._span(expression.source)
        if isinstance(expression, RawIdentifier):
            return Identifier(name=expression.name, source_span=source_span)
        if isinstance(expression, RawLiteral):
            if expression.kind in {
                RawLiteralKind.BIT,
                RawLiteralKind.BIT_VECTOR,
            }:
                unsupported = {
                    char.upper()
                    for char in str(expression.value)
                    if char != "_" and char.upper() not in {"0", "1", "X", "Z"}
                }
                if unsupported:
                    self._raise_semantic(
                        expression.source,
                        "VHDL logic literal uses IEEE 9-state values that have no "
                        "distinct Verilog-2001 representation: " + ", ".join(sorted(unsupported)),
                        "HDLX-VHDL-LOGIC-LITERAL",
                    )
            literal_kind_map = {
                RawLiteralKind.INTEGER: LiteralKind.INTEGER,
                RawLiteralKind.BOOLEAN: LiteralKind.BOOLEAN,
                RawLiteralKind.BIT: LiteralKind.BIT,
                RawLiteralKind.BIT_VECTOR: LiteralKind.BIT_VECTOR,
                RawLiteralKind.STRING: LiteralKind.STRING,
            }
            bit_width = None
            if expression.kind is RawLiteralKind.BIT:
                bit_width = 1
            elif expression.kind is RawLiteralKind.BIT_VECTOR:
                bit_width = len(str(expression.value).replace("_", ""))
            return Literal(
                value=expression.value,
                literal_kind=literal_kind_map[expression.kind],
                bit_width=bit_width,
                source_span=source_span,
            )
        if isinstance(expression, RawIndexExpression):
            base = expression.value
            base_type = (
                symbol_types.get(base.name.casefold()) if isinstance(base, RawIdentifier) else None
            )
            if base_type is None or base_type.kind is not RawTypeKind.VECTOR:
                self._raise_semantic(
                    expression.source,
                    "只有已声明向量对象的单维索引可安全转换；函数调用和类型转换不属于当前 MVP。",
                    "HDLX-VHDL-INDEX-BASE",
                )
            return Index(
                value=self._adapt_expression(expression.value, symbol_types),
                index=self._adapt_expression(expression.index, symbol_types),
                source_span=source_span,
            )
        if isinstance(expression, RawConditionalExpression):
            when_true = self._adapt_expression(expression.when_true, symbol_types)
            when_false = self._adapt_expression(expression.when_false, symbol_types)
            if self._is_signed_expression(
                expression.when_true, symbol_types
            ) and self._is_bit_vector_literal(expression.when_false):
                assert isinstance(when_false, Literal)
                when_false = when_false.model_copy(update={"signed": True})
            if self._is_signed_expression(
                expression.when_false, symbol_types
            ) and self._is_bit_vector_literal(expression.when_true):
                assert isinstance(when_true, Literal)
                when_true = when_true.model_copy(update={"signed": True})
            return TernaryExpr(
                condition=self._adapt_expression(expression.condition, symbol_types),
                when_true=when_true,
                when_false=when_false,
                source_span=source_span,
            )
        if isinstance(expression, RawUnaryExpression):
            operator_map = {
                RawUnaryOperator.NEGATE: UnaryOperator.NEGATE,
                RawUnaryOperator.POSITIVE: UnaryOperator.POSITIVE,
            }
            if expression.operator is RawUnaryOperator.NOT:
                if self._is_four_state_expression(expression.operand, symbol_types):
                    # 对受支持的 0/1/X/Z 子域，Verilog bitwise NOT 与
                    # std_logic_1164 not 的结果一致；弱态字面量已在入口拒绝。
                    operator = UnaryOperator.BITWISE_NOT
                else:
                    operator = (
                        UnaryOperator.LOGICAL_NOT
                        if self._is_boolean(expression.operand, symbol_types)
                        else UnaryOperator.BITWISE_NOT
                    )
            else:
                operator = operator_map[expression.operator]
            operand = self._adapt_expression(expression.operand, symbol_types)
            if expression.operator in {
                RawUnaryOperator.NEGATE,
                RawUnaryOperator.POSITIVE,
            } and self._is_bit_vector_literal(expression.operand):
                assert isinstance(operand, Literal)
                operand = operand.model_copy(update={"signed": True})
            return UnaryExpr(
                operator=operator,
                operand=operand,
                source_span=source_span,
            )
        if isinstance(expression, RawBinaryExpression):
            if expression.operator in {
                RawBinaryOperator.AND,
                RawBinaryOperator.NAND,
                RawBinaryOperator.OR,
                RawBinaryOperator.NOR,
                RawBinaryOperator.XOR,
                RawBinaryOperator.XNOR,
            }:
                left_is_vector = self._is_vector_expression(expression.left, symbol_types)
                right_is_vector = self._is_vector_expression(expression.right, symbol_types)
                if left_is_vector != right_is_vector:
                    self._raise_semantic(
                        expression.source,
                        "VHDL vector/scalar logical overload broadcasts the scalar, "
                        "but canonical replication is not yet represented.",
                        "HDLX-VHDL-VECTOR-LOGIC-WIDTH",
                    )
                if left_is_vector and right_is_vector:
                    left_width = self._vector_width_signature(expression.left, symbol_types)
                    right_width = self._vector_width_signature(expression.right, symbol_types)
                    if left_width is None or left_width != right_width:
                        self._raise_semantic(
                            expression.source,
                            "VHDL vector logical operands must have equal lengths, "
                            "while Verilog would extend mismatched operands.",
                            "HDLX-VHDL-VECTOR-LOGIC-WIDTH",
                        )
            if expression.operator is RawBinaryOperator.MODULO:
                self._raise_semantic(
                    expression.source,
                    "VHDL mod differs from Verilog remainder for negative operands.",
                    "HDLX-VHDL-MODULO-SEMANTICS",
                )
            if expression.operator is RawBinaryOperator.CONCATENATE:
                self._raise_semantic(
                    expression.source,
                    "VHDL concatenation result direction/typing is not yet explicit in "
                    "the canonical expression model.",
                    "HDLX-VHDL-CONCATENATION-TYPE",
                )
            if (
                expression.operator
                in {
                    RawBinaryOperator.ADD,
                    RawBinaryOperator.SUBTRACT,
                }
                and (
                    self._is_vector_expression(expression.left, symbol_types)
                    != self._is_vector_expression(expression.right, symbol_types)
                )
                and not allow_root_mixed_arithmetic
            ):
                self._raise_semantic(
                    expression.source,
                    "numeric_std vector/integer add or subtract first converts the "
                    "integer to the vector width, while Verilog unsized integer "
                    "arithmetic widens the expression.",
                    "HDLX-VHDL-MIXED-ARITHMETIC-WIDTH",
                )
            if expression.operator in {
                RawBinaryOperator.MULTIPLY,
                RawBinaryOperator.DIVIDE,
                RawBinaryOperator.POWER,
            } and (
                self._is_vector_expression(expression.left, symbol_types)
                or self._is_vector_expression(expression.right, symbol_types)
            ):
                self._raise_semantic(
                    expression.source,
                    "vector multiply/divide/power width semantics require explicit "
                    "result sizing not yet represented by the canonical IR.",
                    "HDLX-VHDL-VECTOR-ARITHMETIC-WIDTH",
                )
            left = self._adapt_expression(expression.left, symbol_types)
            right = self._adapt_expression(expression.right, symbol_types)
            # VHDL bit-string literal 会由重载上下文取得 signed/unsigned 类型；
            # canonical Literal 必须显式保存该信息，否则 Verilog 比较会把
            # signed 向量与 unsigned sized literal 一起按 unsigned 解释。
            if (
                self._is_signed_expression(expression.left, symbol_types)
                and isinstance(expression.right, RawLiteral)
                and expression.right.kind is RawLiteralKind.BIT_VECTOR
                and isinstance(right, Literal)
            ):
                right = right.model_copy(update={"signed": True})
            if (
                self._is_signed_expression(expression.right, symbol_types)
                and isinstance(expression.left, RawLiteral)
                and expression.left.kind is RawLiteralKind.BIT_VECTOR
                and isinstance(left, Literal)
            ):
                left = left.model_copy(update={"signed": True})
            if expression.operator is RawBinaryOperator.CONCATENATE:
                parts = []
                parts.extend(left.parts if isinstance(left, Concatenation) else [left])
                parts.extend(right.parts if isinstance(right, Concatenation) else [right])
                return Concatenation(parts=parts, source_span=source_span)

            boolean_operands = self._is_boolean(expression.left, symbol_types) and self._is_boolean(
                expression.right, symbol_types
            )
            if expression.operator in {RawBinaryOperator.NAND, RawBinaryOperator.NOR}:
                base_operator = (
                    BinaryOperator.LOGICAL_AND
                    if boolean_operands and expression.operator is RawBinaryOperator.NAND
                    else BinaryOperator.LOGICAL_OR
                    if boolean_operands
                    else BinaryOperator.BITWISE_AND
                    if expression.operator is RawBinaryOperator.NAND
                    else BinaryOperator.BITWISE_OR
                )
                combined = BinaryExpr(
                    left=left,
                    operator=base_operator,
                    right=right,
                    source_span=source_span,
                )
                return UnaryExpr(
                    operator=(
                        UnaryOperator.LOGICAL_NOT if boolean_operands else UnaryOperator.BITWISE_NOT
                    ),
                    operand=combined,
                    source_span=source_span,
                )

            operator_map = {
                RawBinaryOperator.ADD: BinaryOperator.ADD,
                RawBinaryOperator.SUBTRACT: BinaryOperator.SUBTRACT,
                RawBinaryOperator.MULTIPLY: BinaryOperator.MULTIPLY,
                RawBinaryOperator.DIVIDE: BinaryOperator.DIVIDE,
                RawBinaryOperator.MODULO: BinaryOperator.MODULO,
                RawBinaryOperator.POWER: BinaryOperator.POWER,
                RawBinaryOperator.XOR: BinaryOperator.BITWISE_XOR,
                RawBinaryOperator.XNOR: BinaryOperator.BITWISE_XNOR,
                RawBinaryOperator.EQUAL: BinaryOperator.EQUAL,
                RawBinaryOperator.NOT_EQUAL: BinaryOperator.NOT_EQUAL,
                RawBinaryOperator.LESS_THAN: BinaryOperator.LESS_THAN,
                RawBinaryOperator.LESS_EQUAL: BinaryOperator.LESS_EQUAL,
                RawBinaryOperator.GREATER_THAN: BinaryOperator.GREATER_THAN,
                RawBinaryOperator.GREATER_EQUAL: BinaryOperator.GREATER_EQUAL,
            }
            if expression.operator is RawBinaryOperator.AND:
                operator = (
                    BinaryOperator.LOGICAL_AND if boolean_operands else BinaryOperator.BITWISE_AND
                )
            elif expression.operator is RawBinaryOperator.OR:
                operator = (
                    BinaryOperator.LOGICAL_OR if boolean_operands else BinaryOperator.BITWISE_OR
                )
            else:
                operator = operator_map[expression.operator]
            if expression.operator in {
                RawBinaryOperator.EQUAL,
                RawBinaryOperator.NOT_EQUAL,
            }:
                has_four_state_operand = self._is_four_state_expression(
                    expression.left, symbol_types
                ) or self._is_four_state_expression(expression.right, symbol_types)
                has_numeric_vector_operand = self._is_numeric_vector_expression(
                    expression.left, symbol_types
                ) or self._is_numeric_vector_expression(expression.right, symbol_types)
                if (
                    has_four_state_operand
                    and not has_numeric_vector_operand
                    and (
                        self._is_vector_expression(expression.left, symbol_types)
                        or self._is_vector_expression(expression.right, symbol_types)
                    )
                ):
                    left_width = self._vector_width_signature(expression.left, symbol_types)
                    right_width = self._vector_width_signature(expression.right, symbol_types)
                    if left_width is None or left_width != right_width:
                        self._raise_semantic(
                            expression.source,
                            "VHDL predefined vector equality first compares array "
                            "lengths, while Verilog equality extends operands; equal "
                            "width must be statically provable.",
                            "HDLX-VHDL-VECTOR-COMPARISON-WIDTH",
                        )
                if has_four_state_operand and has_numeric_vector_operand:
                    # numeric_std 对 meta value 的等于返回 false、不等于返回 true；
                    # 先保留普通比较产生的 X，再用 case comparison 归一成 boolean。
                    relation = BinaryExpr(
                        left=left,
                        operator=operator,
                        right=right,
                        source_span=source_span,
                    )
                    return BinaryExpr(
                        left=relation,
                        operator=(
                            BinaryOperator.CASE_EQUAL
                            if expression.operator is RawBinaryOperator.EQUAL
                            else BinaryOperator.CASE_NOT_EQUAL
                        ),
                        right=Literal(
                            value=(
                                True if expression.operator is RawBinaryOperator.EQUAL else False
                            ),
                            source_span=source_span,
                        ),
                        source_span=source_span,
                    )
                if has_four_state_operand:
                    operator = (
                        BinaryOperator.CASE_EQUAL
                        if expression.operator is RawBinaryOperator.EQUAL
                        else BinaryOperator.CASE_NOT_EQUAL
                    )
            if expression.operator in {
                RawBinaryOperator.LESS_THAN,
                RawBinaryOperator.LESS_EQUAL,
                RawBinaryOperator.GREATER_THAN,
                RawBinaryOperator.GREATER_EQUAL,
            } and (
                self._is_four_state_expression(expression.left, symbol_types)
                or self._is_four_state_expression(expression.right, symbol_types)
            ):
                if not (
                    self._is_numeric_vector_expression(expression.left, symbol_types)
                    or self._is_numeric_vector_expression(expression.right, symbol_types)
                ):
                    self._raise_semantic(
                        expression.source,
                        "std_logic relational ordering over meta values cannot be "
                        "represented by Verilog-2001 numeric comparison.",
                        "HDLX-VHDL-FOUR-STATE-RELATIONAL",
                    )
                relation = BinaryExpr(
                    left=left,
                    operator=operator,
                    right=right,
                    source_span=source_span,
                )
                return BinaryExpr(
                    left=relation,
                    operator=BinaryOperator.CASE_EQUAL,
                    right=Literal(value=True, source_span=source_span),
                    source_span=source_span,
                )
            return BinaryExpr(
                left=left,
                operator=operator,
                right=right,
                source_span=source_span,
            )
        raise UnsupportedConstructError(
            f"Raw expression {type(expression).__name__} 尚无 canonical 映射。",
            code="HDLX-VHDL-RAW-EXPRESSION",
        )

    def _adapt_assignment_value(
        self,
        target: RawExpression,
        value: RawExpression,
        symbol_types: Mapping[str, RawType],
    ) -> Identifier | Literal | UnaryExpr | BinaryExpr | TernaryExpr | Concatenation | Index:
        """仅在赋值边界可证明截断等价时保留 mixed vector/integer ``+/-``。"""

        target_width = self._vector_width_signature(target, symbol_types)
        value_is_vector = self._is_vector_expression(value, symbol_types)
        value_width = self._vector_width_signature(value, symbol_types)
        allow_root_mixed = False
        if isinstance(value, RawBinaryExpression) and value.operator in {
            RawBinaryOperator.ADD,
            RawBinaryOperator.SUBTRACT,
        }:
            left_is_vector = self._is_vector_expression(value.left, symbol_types)
            right_is_vector = self._is_vector_expression(value.right, symbol_types)
            if left_is_vector != right_is_vector:
                vector_operand = value.left if left_is_vector else value.right
                operand_width = self._vector_width_signature(vector_operand, symbol_types)
                # numeric_std 的结果宽度等于 vector operand；Verilog 的 unsized
                # integer 会扩宽中间式，但在同宽赋值边界截断后的 bit pattern
                # 等价。嵌套比较或不同宽目标没有这个安全边界，继续显式拒绝。
                allow_root_mixed = target_width is not None and target_width == operand_width
        adapted = self._adapt_expression(
            value,
            symbol_types,
            allow_root_mixed_arithmetic=allow_root_mixed,
        )
        if target_width is not None and value_is_vector and value_width != target_width:
            self._raise_semantic(
                value.source,
                "VHDL vector assignment requires equal array lengths, while Verilog "
                "assignment would extend or truncate; equal width must be provable "
                "for all legal generic values.",
                "HDLX-VHDL-ASSIGNMENT-WIDTH",
            )
        return adapted

    def _is_boolean(self, expression: RawExpression, symbol_types: Mapping[str, RawType]) -> bool:
        if isinstance(expression, RawLiteral):
            return expression.kind is RawLiteralKind.BOOLEAN
        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            return raw_type is not None and raw_type.kind is RawTypeKind.BOOLEAN
        if isinstance(expression, RawUnaryExpression):
            return self._is_boolean(expression.operand, symbol_types)
        if isinstance(expression, RawBinaryExpression):
            if expression.operator in {
                RawBinaryOperator.EQUAL,
                RawBinaryOperator.NOT_EQUAL,
                RawBinaryOperator.LESS_THAN,
                RawBinaryOperator.LESS_EQUAL,
                RawBinaryOperator.GREATER_THAN,
                RawBinaryOperator.GREATER_EQUAL,
            }:
                return True
            if expression.operator in {
                RawBinaryOperator.AND,
                RawBinaryOperator.NAND,
                RawBinaryOperator.OR,
                RawBinaryOperator.NOR,
                RawBinaryOperator.XOR,
                RawBinaryOperator.XNOR,
            }:
                return self._is_boolean(expression.left, symbol_types) and self._is_boolean(
                    expression.right, symbol_types
                )
        return False

    def _is_signed_expression(
        self, expression: RawExpression, symbol_types: Mapping[str, RawType]
    ) -> bool:
        """保守识别结果仍保持 signed 向量语义的 Raw 表达式。"""

        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            return raw_type is not None and raw_type.kind is RawTypeKind.VECTOR and raw_type.signed
        if isinstance(expression, RawUnaryExpression):
            if expression.operator in {
                RawUnaryOperator.NEGATE,
                RawUnaryOperator.POSITIVE,
            } and self._is_bit_vector_literal(expression.operand):
                # numeric_std 的一元正负号只为 SIGNED 定义，位串由该
                # overload 取得 signed 上下文。
                return True
            return self._is_signed_expression(expression.operand, symbol_types)
        if isinstance(expression, RawConditionalExpression):
            true_signed = self._is_signed_expression(expression.when_true, symbol_types)
            false_signed = self._is_signed_expression(expression.when_false, symbol_types)
            return (
                (true_signed and false_signed)
                or (true_signed and self._is_bit_vector_literal(expression.when_false))
                or (false_signed and self._is_bit_vector_literal(expression.when_true))
            )
        if isinstance(expression, RawBinaryExpression):
            if expression.operator in {
                RawBinaryOperator.EQUAL,
                RawBinaryOperator.NOT_EQUAL,
                RawBinaryOperator.LESS_THAN,
                RawBinaryOperator.LESS_EQUAL,
                RawBinaryOperator.GREATER_THAN,
                RawBinaryOperator.GREATER_EQUAL,
            }:
                return False
            left_signed = self._is_signed_expression(expression.left, symbol_types)
            right_signed = self._is_signed_expression(expression.right, symbol_types)
            return (
                (left_signed and right_signed)
                or (left_signed and self._is_bit_vector_literal(expression.right))
                or (right_signed and self._is_bit_vector_literal(expression.left))
            )
        return False

    @staticmethod
    def _is_bit_vector_literal(expression: RawExpression) -> bool:
        return isinstance(expression, RawLiteral) and expression.kind is RawLiteralKind.BIT_VECTOR

    def _is_four_state_expression(
        self, expression: RawExpression, symbol_types: Mapping[str, RawType]
    ) -> bool:
        """识别可能包含 meta value 的 std_logic 类表达式。"""

        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            return raw_type is not None and raw_type.four_state
        if isinstance(expression, RawLiteral):
            # X/Z 不属于 VHDL 两态 bit 类型，因此位/位串中出现任一值即可
            # 证明其 overload 是四态，即使比较两侧都只由字面量派生
            # （例如 ``(not 'X') = 'X'``）。
            if expression.kind in {RawLiteralKind.BIT, RawLiteralKind.BIT_VECTOR}:
                literal = str(expression.value).replace("_", "").casefold()
                return "x" in literal or "z" in literal
            # 0/1 字面量仍依赖上下文；这些情形由已声明的 operand 或 target
            # 提供四态信息。
            return False
        if isinstance(expression, RawIndexExpression):
            return self._is_four_state_expression(expression.value, symbol_types)
        if isinstance(expression, RawUnaryExpression):
            if expression.operator in {
                RawUnaryOperator.NEGATE,
                RawUnaryOperator.POSITIVE,
            } and self._is_bit_vector_literal(expression.operand):
                # numeric_std 只为 SIGNED 定义一元正负号，因此即使位串字面量
                # 自身尚未定型，也会从该 overload 获得四态有符号向量上下文。
                return True
            return self._is_four_state_expression(expression.operand, symbol_types)
        if isinstance(expression, RawConditionalExpression):
            return self._is_four_state_expression(
                expression.when_true, symbol_types
            ) or self._is_four_state_expression(expression.when_false, symbol_types)
        if isinstance(expression, RawBinaryExpression):
            return self._is_four_state_expression(
                expression.left, symbol_types
            ) or self._is_four_state_expression(expression.right, symbol_types)
        return False

    def _is_numeric_vector_expression(
        self, expression: RawExpression, symbol_types: Mapping[str, RawType]
    ) -> bool:
        """识别由 numeric_std signed/unsigned 运算产生的向量表达式。"""

        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            return (
                raw_type is not None
                and raw_type.kind is RawTypeKind.VECTOR
                and raw_type.source_name.casefold() in {"signed", "unsigned"}
            )
        if isinstance(expression, RawUnaryExpression):
            if expression.operator in {
                RawUnaryOperator.NEGATE,
                RawUnaryOperator.POSITIVE,
            } and self._is_bit_vector_literal(expression.operand):
                return True
            return self._is_numeric_vector_expression(expression.operand, symbol_types)
        if isinstance(expression, RawConditionalExpression):
            return self._is_numeric_vector_expression(
                expression.when_true, symbol_types
            ) or self._is_numeric_vector_expression(expression.when_false, symbol_types)
        if isinstance(expression, RawBinaryExpression):
            if expression.operator in {
                RawBinaryOperator.EQUAL,
                RawBinaryOperator.NOT_EQUAL,
                RawBinaryOperator.LESS_THAN,
                RawBinaryOperator.LESS_EQUAL,
                RawBinaryOperator.GREATER_THAN,
                RawBinaryOperator.GREATER_EQUAL,
                RawBinaryOperator.CONCATENATE,
            }:
                return False
            return self._is_numeric_vector_expression(
                expression.left, symbol_types
            ) or self._is_numeric_vector_expression(expression.right, symbol_types)
        return False

    def _is_vector_expression(
        self, expression: RawExpression, symbol_types: Mapping[str, RawType]
    ) -> bool:
        """保守识别需要显式位宽规则的向量表达式。"""

        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            return raw_type is not None and raw_type.kind is RawTypeKind.VECTOR
        if isinstance(expression, RawLiteral):
            return expression.kind is RawLiteralKind.BIT_VECTOR
        if isinstance(expression, RawConditionalExpression):
            return self._is_vector_expression(
                expression.when_true, symbol_types
            ) or self._is_vector_expression(expression.when_false, symbol_types)
        if isinstance(expression, RawUnaryExpression):
            return self._is_vector_expression(expression.operand, symbol_types)
        if isinstance(expression, RawBinaryExpression):
            return self._is_vector_expression(
                expression.left, symbol_types
            ) or self._is_vector_expression(expression.right, symbol_types)
        return False

    def _vector_width_signature(
        self, expression: RawExpression, symbol_types: Mapping[str, RawType]
    ) -> tuple[object, ...] | None:
        """仅在可证明时返回向量宽度的结构化签名。"""

        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            if (
                raw_type is None
                or raw_type.kind is not RawTypeKind.VECTOR
                or raw_type.range is None
            ):
                return None
            return self._range_width_signature(raw_type.range)
        if isinstance(expression, RawLiteral):
            if expression.kind is not RawLiteralKind.BIT_VECTOR:
                return None
            return ("constant", len(str(expression.value).replace("_", "")))
        if isinstance(expression, RawUnaryExpression):
            return self._vector_width_signature(expression.operand, symbol_types)
        if isinstance(expression, RawConditionalExpression):
            when_true = self._vector_width_signature(expression.when_true, symbol_types)
            when_false = self._vector_width_signature(expression.when_false, symbol_types)
            return when_true if when_true is not None and when_true == when_false else None
        if isinstance(expression, RawBinaryExpression) and expression.operator in {
            RawBinaryOperator.ADD,
            RawBinaryOperator.SUBTRACT,
        }:
            left_is_vector = self._is_vector_expression(expression.left, symbol_types)
            right_is_vector = self._is_vector_expression(expression.right, symbol_types)
            left = self._vector_width_signature(expression.left, symbol_types)
            right = self._vector_width_signature(expression.right, symbol_types)
            if left_is_vector and right_is_vector:
                return left if left is not None and left == right else None
            if left_is_vector != right_is_vector:
                return left if left_is_vector else right
            return None
        if isinstance(expression, RawBinaryExpression) and expression.operator in {
            RawBinaryOperator.AND,
            RawBinaryOperator.NAND,
            RawBinaryOperator.OR,
            RawBinaryOperator.NOR,
            RawBinaryOperator.XOR,
            RawBinaryOperator.XNOR,
        }:
            left = self._vector_width_signature(expression.left, symbol_types)
            right = self._vector_width_signature(expression.right, symbol_types)
            return left if left is not None and left == right else None
        return None

    def _range_width_signature(self, raw_range: RawRange) -> tuple[object, ...]:
        """将常量范围化为宽度，其余范围保留忽略源码位置的结构。"""

        left = raw_range.left
        right = raw_range.right
        if (
            isinstance(left, RawLiteral)
            and left.kind is RawLiteralKind.INTEGER
            and isinstance(left.value, int)
            and isinstance(right, RawLiteral)
            and right.kind is RawLiteralKind.INTEGER
            and isinstance(right.value, int)
        ):
            width = (
                right.value - left.value + 1
                if raw_range.direction is RawRangeDirection.TO
                else left.value - right.value + 1
            )
            return ("constant", max(width, 0))
        # array 长度只由两个端点之差的绝对值决定；方向属于索引语义，
        # 不属于宽度。按稳定 repr 排序后，A downto B 与 B to A 可证明等宽。
        endpoints = sorted(
            (
                self._raw_expression_signature(left),
                self._raw_expression_signature(right),
            ),
            key=repr,
        )
        return ("range_width", endpoints[0], endpoints[1])

    def _bound_range_width_signature(
        self,
        raw_range: RawRange,
        identifier_bindings: Mapping[str, tuple[object, ...]],
    ) -> tuple[object, ...]:
        """替换 child generic 后生成调用方作用域中的端口宽度签名。"""

        left = self._bound_raw_expression_signature(raw_range.left, identifier_bindings)
        right = self._bound_raw_expression_signature(raw_range.right, identifier_bindings)
        left_value = self._constant_integer_signature_value(left)
        right_value = self._constant_integer_signature_value(right)
        if left_value is not None and right_value is not None:
            width = (
                right_value - left_value + 1
                if raw_range.direction is RawRangeDirection.TO
                else left_value - right_value + 1
            )
            return ("constant", max(width, 0))
        endpoints = sorted((left, right), key=repr)
        return ("range_width", endpoints[0], endpoints[1])

    def _range_is_provably_non_null(
        self,
        raw_range: RawRange,
        symbol_types: Mapping[str, RawType],
    ) -> bool:
        """利用整数 subtype 下界证明 packed vector 对所有合法 generic 非空。"""

        left_lower, left_upper = self._integer_interval(raw_range.left, symbol_types)
        right_lower, right_upper = self._integer_interval(raw_range.right, symbol_types)
        if raw_range.direction is RawRangeDirection.TO:
            return (
                right_lower is not None and left_upper is not None and (right_lower >= left_upper)
            )
        return left_lower is not None and right_upper is not None and (left_lower >= right_upper)

    def _integer_interval(
        self,
        expression: RawExpression,
        symbol_types: Mapping[str, RawType],
    ) -> tuple[int | None, int | None]:
        """计算足以证明范围非空的保守整数区间。"""

        if (
            isinstance(expression, RawLiteral)
            and expression.kind is RawLiteralKind.INTEGER
            and isinstance(expression.value, int)
        ):
            return expression.value, expression.value
        if isinstance(expression, RawIdentifier):
            raw_type = symbol_types.get(expression.name.casefold())
            if raw_type is None or raw_type.kind is not RawTypeKind.INTEGER:
                return None, None
            source_name = raw_type.source_name.casefold()
            if source_name == "positive":
                return 1, None
            if source_name == "natural":
                return 0, None
            return None, None
        if isinstance(expression, RawUnaryExpression):
            lower, upper = self._integer_interval(expression.operand, symbol_types)
            if expression.operator is RawUnaryOperator.POSITIVE:
                return lower, upper
            if expression.operator is RawUnaryOperator.NEGATE:
                return (
                    None if upper is None else -upper,
                    None if lower is None else -lower,
                )
            return None, None
        if isinstance(expression, RawBinaryExpression):
            left_lower, left_upper = self._integer_interval(expression.left, symbol_types)
            right_lower, right_upper = self._integer_interval(expression.right, symbol_types)
            if expression.operator is RawBinaryOperator.ADD:
                return (
                    None if left_lower is None or right_lower is None else left_lower + right_lower,
                    None if left_upper is None or right_upper is None else left_upper + right_upper,
                )
            if expression.operator is RawBinaryOperator.SUBTRACT:
                return (
                    None if left_lower is None or right_upper is None else left_lower - right_upper,
                    None if left_upper is None or right_lower is None else left_upper - right_lower,
                )
            if (
                expression.operator is RawBinaryOperator.MULTIPLY
                and left_lower is not None
                and right_lower is not None
                and left_lower >= 0
                and right_lower >= 0
            ):
                lower = left_lower * right_lower
                if left_upper == 0 or right_upper == 0:
                    return lower, 0
                upper = (
                    None if left_upper is None or right_upper is None else left_upper * right_upper
                )
                return lower, upper
        return None, None

    def _raw_expression_signature(self, expression: RawExpression) -> tuple[object, ...]:
        """为范围表达式生成忽略 source location 的保守结构签名。"""

        if isinstance(expression, RawIdentifier):
            return ("identifier", expression.name.casefold())
        if isinstance(expression, RawLiteral):
            return ("literal", expression.kind.value, expression.value)
        if isinstance(expression, RawUnaryExpression):
            return (
                "unary",
                expression.operator.value,
                self._raw_expression_signature(expression.operand),
            )
        if isinstance(expression, RawBinaryExpression):
            return (
                "binary",
                expression.operator.value,
                self._raw_expression_signature(expression.left),
                self._raw_expression_signature(expression.right),
            )
        if isinstance(expression, RawIndexExpression):
            return (
                "index",
                self._raw_expression_signature(expression.value),
                self._raw_expression_signature(expression.index),
            )
        return (
            "conditional",
            self._raw_expression_signature(expression.condition),
            self._raw_expression_signature(expression.when_true),
            self._raw_expression_signature(expression.when_false),
        )

    def _bound_raw_expression_signature(
        self,
        expression: RawExpression,
        identifier_bindings: Mapping[str, tuple[object, ...]],
    ) -> tuple[object, ...]:
        """生成表达式签名，并只替换当前 child generic 名称。"""

        if isinstance(expression, RawIdentifier):
            return identifier_bindings.get(
                expression.name.casefold(),
                ("identifier", expression.name.casefold()),
            )
        if isinstance(expression, RawLiteral):
            return ("literal", expression.kind.value, expression.value)
        if isinstance(expression, RawUnaryExpression):
            return (
                "unary",
                expression.operator.value,
                self._bound_raw_expression_signature(expression.operand, identifier_bindings),
            )
        if isinstance(expression, RawBinaryExpression):
            return (
                "binary",
                expression.operator.value,
                self._bound_raw_expression_signature(expression.left, identifier_bindings),
                self._bound_raw_expression_signature(expression.right, identifier_bindings),
            )
        if isinstance(expression, RawIndexExpression):
            return (
                "index",
                self._bound_raw_expression_signature(expression.value, identifier_bindings),
                self._bound_raw_expression_signature(expression.index, identifier_bindings),
            )
        return (
            "conditional",
            self._bound_raw_expression_signature(expression.condition, identifier_bindings),
            self._bound_raw_expression_signature(expression.when_true, identifier_bindings),
            self._bound_raw_expression_signature(expression.when_false, identifier_bindings),
        )

    @classmethod
    def _constant_integer_signature_value(cls, signature: tuple[object, ...]) -> int | None:
        """只折叠不会引入 VHDL/Verilog差异的整数常量算术。"""

        if (
            len(signature) == 3
            and signature[0] == "literal"
            and signature[1] == RawLiteralKind.INTEGER.value
            and isinstance(signature[2], int)
        ):
            return signature[2]
        if len(signature) == 3 and signature[0] == "unary":
            operand = signature[2]
            if not isinstance(operand, tuple):
                return None
            value = cls._constant_integer_signature_value(operand)
            if value is None:
                return None
            if signature[1] == RawUnaryOperator.POSITIVE.value:
                return value
            if signature[1] == RawUnaryOperator.NEGATE.value:
                return -value
            return None
        if len(signature) == 4 and signature[0] == "binary":
            left = signature[2]
            right = signature[3]
            if not isinstance(left, tuple) or not isinstance(right, tuple):
                return None
            left_value = cls._constant_integer_signature_value(left)
            right_value = cls._constant_integer_signature_value(right)
            if left_value is None or right_value is None:
                return None
            if signature[1] == RawBinaryOperator.ADD.value:
                return left_value + right_value
            if signature[1] == RawBinaryOperator.SUBTRACT.value:
                return left_value - right_value
            if signature[1] == RawBinaryOperator.MULTIPLY.value:
                return left_value * right_value
        return None

    def _raw_default_signature(self, expression: RawExpression | None) -> tuple[object, ...] | None:
        """比较接口默认值时忽略源码位置，但不做不可靠的代数等价猜测。"""

        if expression is None:
            return None
        return self._raw_expression_signature(expression)

    def _raw_type_signature(self, raw_type: RawType) -> tuple[object, ...]:
        """生成足以保守证明 component/entity subtype 等价的结构签名。"""

        range_signature = None
        if raw_type.range is not None:
            range_signature = (
                raw_type.range.direction.value,
                self._raw_expression_signature(raw_type.range.left),
                self._raw_expression_signature(raw_type.range.right),
            )
        return (
            raw_type.kind.value,
            raw_type.source_name.casefold(),
            raw_type.signed,
            raw_type.four_state,
            range_signature,
        )

    @staticmethod
    def _span(source: RawSourceLocation | None) -> SourceSpan | None:
        if source is None:
            return None
        location = SourceLocation(file=str(source.file), line=source.line, column=source.column)
        return SourceSpan(start=location, end=location.model_copy())

    @staticmethod
    def _raise_semantic(source: RawSourceLocation | None, message: str, code: str) -> None:
        raise SemanticError(
            message,
            code=code,
            file=str(source.file) if source is not None else None,
            line=source.line if source is not None else None,
            column=source.column if source is not None else None,
        )


__all__ = ["VhdlAdapter"]
