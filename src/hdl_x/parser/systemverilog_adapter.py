"""SystemVerilog Slang Raw syntax 到语言无关 Canonical RTL IR。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from hdl_x.diagnostics import UnsupportedConstructError
from hdl_x.ir import (
    ActiveLevel,
    AssignmentKind,
    BinaryExpr,
    BinaryOperator,
    CaseAlternative,
    CaseStatement,
    CombinationalProcess,
    Concatenation,
    ContinuousAssignment,
    Design,
    EdgeKind,
    ExpressionNode,
    Identifier,
    IfStatement,
    Index,
    Instance,
    IntegerType,
    Literal,
    LiteralKind,
    Module,
    ModuleItem,
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
    ScalarType,
    SequentialProcess,
    Signal,
    Slice,
    SourceLocation,
    SourceSpan,
    StatementNode,
    TernaryExpr,
    UnaryExpr,
    UnaryOperator,
    VectorRange,
    VectorType,
)
from hdl_x.parser.base import ParserAdapter
from hdl_x.parser.slang import (
    RawSourceSpan,
    RawSystemVerilogDesign,
    RawSystemVerilogModule,
)

JsonObject = dict[str, Any]

_BINARY_OPERATORS: dict[str, BinaryOperator] = {
    "AddExpression": BinaryOperator.ADD,
    "SubtractExpression": BinaryOperator.SUBTRACT,
    "MultiplyExpression": BinaryOperator.MULTIPLY,
    "DivideExpression": BinaryOperator.DIVIDE,
    "ModExpression": BinaryOperator.MODULO,
    "BinaryAndExpression": BinaryOperator.BITWISE_AND,
    "BinaryOrExpression": BinaryOperator.BITWISE_OR,
    "BinaryXorExpression": BinaryOperator.BITWISE_XOR,
    "BinaryXnorExpression": BinaryOperator.BITWISE_XNOR,
    "LogicalAndExpression": BinaryOperator.LOGICAL_AND,
    "LogicalOrExpression": BinaryOperator.LOGICAL_OR,
    "EqualityExpression": BinaryOperator.EQUAL,
    "InequalityExpression": BinaryOperator.NOT_EQUAL,
    "CaseEqualityExpression": BinaryOperator.CASE_EQUAL,
    "CaseInequalityExpression": BinaryOperator.CASE_NOT_EQUAL,
    "LessThanExpression": BinaryOperator.LESS_THAN,
    "LessThanEqualExpression": BinaryOperator.LESS_EQUAL,
    "GreaterThanExpression": BinaryOperator.GREATER_THAN,
    "GreaterThanEqualExpression": BinaryOperator.GREATER_EQUAL,
    "LogicalShiftLeftExpression": BinaryOperator.SHIFT_LEFT,
    "LogicalShiftRightExpression": BinaryOperator.SHIFT_RIGHT,
    "ArithmeticShiftRightExpression": BinaryOperator.ARITHMETIC_SHIFT_RIGHT,
}

_UNARY_OPERATORS: dict[str, UnaryOperator] = {
    "UnaryLogicalNotExpression": UnaryOperator.LOGICAL_NOT,
    "UnaryBitwiseNotExpression": UnaryOperator.BITWISE_NOT,
    "UnaryPlusExpression": UnaryOperator.POSITIVE,
    "UnaryMinusExpression": UnaryOperator.NEGATE,
    "UnaryAndExpression": UnaryOperator.REDUCTION_AND,
    "UnaryBitwiseAndExpression": UnaryOperator.REDUCTION_AND,
    "UnaryOrExpression": UnaryOperator.REDUCTION_OR,
    "UnaryBitwiseOrExpression": UnaryOperator.REDUCTION_OR,
    "UnaryXorExpression": UnaryOperator.REDUCTION_XOR,
    "UnaryBitwiseXorExpression": UnaryOperator.REDUCTION_XOR,
}


class SystemVerilogAdapter(ParserAdapter[RawSystemVerilogDesign]):
    """把不含 pyslang 对象的 Raw syntax 规范化为现有 Canonical IR。"""

    def __init__(self) -> None:
        self._source_span: SourceSpan | None = None
        self._localparams: dict[str, ExpressionNode] = {}
        self._all_localparam_names: set[str] = set()
        self._declared_types: dict[str, ScalarType | VectorType | IntegerType] = {}

    def adapt(self, representation: RawSystemVerilogDesign) -> Design:
        modules = [self._adapt_module(module) for module in representation.modules]
        top = representation.top_names[0] if len(representation.top_names) == 1 else None
        return Design(modules=modules, top=top)

    def _adapt_module(self, raw: RawSystemVerilogModule) -> Module:
        self._source_span = self._span(raw.source)
        self._localparams = {}
        self._declared_types = {}
        payload = raw.syntax
        self._expect_kind(payload, "ModuleDeclaration")
        header = self._object(payload.get("header"), "module header")
        self._all_localparam_names = self._collect_localparam_names(header, payload)

        parameters: list[Parameter] = []
        header_parameters = self._parameter_declarations(header.get("parameters"))
        for declaration in header_parameters:
            self._adapt_parameter_declaration(declaration, parameters)

        ports = self._adapt_ports(header.get("ports"))
        self._declared_types.update({port.name: port.rtl_type for port in ports})
        signals: list[Signal] = []
        items: list[ModuleItem] = []
        for member in self._node_list(payload.get("members")):
            kind = self._kind(member)
            if kind == "ParameterDeclaration":
                self._adapt_parameter_declaration(member, parameters)
            elif kind in {"DataDeclaration", "NetDeclaration"}:
                declarations = self._adapt_signal_declaration(member)
                signals.extend(declarations)
                self._declared_types.update(
                    {declaration.name: declaration.rtl_type for declaration in declarations}
                )
            elif kind == "ContinuousAssign":
                items.extend(self._adapt_continuous_assign(member))
            elif kind == "AlwaysCombBlock":
                items.append(self._adapt_always_comb(member))
            elif kind == "AlwaysFFBlock":
                items.append(self._adapt_always_ff(member))
            elif kind == "HierarchyInstantiation":
                items.extend(self._adapt_instances(member))
            else:
                self._unsupported(
                    f"module member {kind} 不在 SystemVerilog v0.2 MVP 内",
                    code="HDLX-SV-MODULE-MEMBER",
                )

        return Module(
            name=raw.name,
            parameters=parameters,
            ports=ports,
            signals=signals,
            items=items,
            source_span=self._source_span,
        )

    def _collect_localparam_names(
        self,
        header: JsonObject,
        module: JsonObject,
    ) -> set[str]:
        names: set[str] = set()
        declarations = [
            *self._parameter_declarations(header.get("parameters")),
            *[
                member
                for member in self._node_list(module.get("members"))
                if self._kind(member) == "ParameterDeclaration"
            ],
        ]
        for declaration in declarations:
            keyword = self._object(declaration.get("keyword"), "parameter keyword")
            if self._kind(keyword) != "LocalParamKeyword":
                continue
            for declarator in self._node_list(declaration.get("declarators")):
                names.add(self._token_text(declarator.get("name"), "localparam name"))
        return names

    def _parameter_declarations(self, value: object) -> list[JsonObject]:
        if value is None:
            return []
        container = self._object(value, "parameter port list")
        if self._kind(container) != "ParameterPortList":
            self._unsupported(
                "只支持 ANSI parameter port list",
                code="HDLX-SV-PARAMETER-LIST",
            )
        return [
            node
            for node in self._node_list(container.get("declarations"))
            if self._kind(node) == "ParameterDeclaration"
        ]

    def _adapt_parameter_declaration(
        self,
        declaration: JsonObject,
        parameters: list[Parameter],
    ) -> None:
        keyword = self._object(declaration.get("keyword"), "parameter keyword")
        keyword_kind = self._kind(keyword)
        if keyword_kind not in {"ParameterKeyword", "LocalParamKeyword"}:
            self._unsupported(
                "type parameter 不在 v0.2 MVP 内",
                code="HDLX-SV-TYPE-PARAMETER",
            )
        rtl_type = self._adapt_type(self._object(declaration.get("type"), "parameter type"))
        if not isinstance(rtl_type, IntegerType | ScalarType | VectorType):
            self._unsupported(
                "parameter 类型必须是 integral",
                code="HDLX-SV-PARAMETER-TYPE",
            )

        for declarator in self._node_list(declaration.get("declarators")):
            name = self._token_text(declarator.get("name"), "parameter name")
            initializer = declarator.get("initializer")
            default = None
            if initializer is not None:
                clause = self._object(initializer, "parameter initializer")
                default = self._adapt_expression(
                    self._object(clause.get("expr"), "parameter expression")
                )
            if keyword_kind == "LocalParamKeyword":
                if default is None:
                    self._unsupported(
                        f"localparam {name!r} 缺少常量表达式",
                        code="HDLX-SV-LOCALPARAM-DEFAULT",
                    )
                if self._contains_any_identifier(default, self._all_localparam_names):
                    self._unsupported(
                        f"localparam {name!r} 无法按声明顺序安全内联",
                        code="HDLX-SV-LOCALPARAM-CYCLE",
                    )
                self._localparams[name] = default
                continue
            parameters.append(
                Parameter(
                    name=name,
                    rtl_type=rtl_type.model_copy(deep=True),
                    default=default,
                    source_span=self._source_span,
                )
            )

    def _adapt_ports(self, value: object) -> list[Port]:
        if value is None:
            return []
        port_list = self._object(value, "ANSI port list")
        if self._kind(port_list) != "AnsiPortList":
            self._unsupported(
                "只支持 ANSI port declaration",
                code="HDLX-SV-NONANSI-PORT",
            )

        ports: list[Port] = []
        previous_direction: PortDirection | None = None
        previous_type: ScalarType | VectorType | IntegerType | None = None
        for node in self._node_list(port_list.get("ports")):
            if self._kind(node) != "ImplicitAnsiPort":
                self._unsupported(
                    "显式/接口 ANSI port 不在 v0.2 MVP 内",
                    code="HDLX-SV-ANSI-PORT",
                )
            header = self._object(node.get("header"), "ANSI port header")
            direction_node = header.get("direction")
            if direction_node is None:
                if previous_direction is None or previous_type is None:
                    self._unsupported(
                        "ANSI port 省略方向但没有可继承声明",
                        code="HDLX-SV-PORT-INHERITANCE",
                    )
                direction = previous_direction
            else:
                direction = self._adapt_direction(self._object(direction_node, "port direction"))

            if self._kind(header) == "NetPortHeader":
                net_type = header.get("netType")
                if (
                    net_type is not None
                    and self._kind(self._object(net_type, "net type")) != "WireKeyword"
                ):
                    self._unsupported(
                        "只支持 wire net port",
                        code="HDLX-SV-NET-TYPE",
                    )
            elif self._kind(header) != "VariablePortHeader":
                self._unsupported(
                    f"port header {self._kind(header)} 不在 v0.2 MVP 内",
                    code="HDLX-SV-PORT-HEADER",
                )

            data_type = self._object(header.get("dataType"), "port data type")
            inherits_type = (
                direction_node is None
                and self._kind(data_type) == "ImplicitType"
                and not data_type.get("dimensions")
            )
            if inherits_type:
                assert previous_type is not None
                rtl_type = previous_type.model_copy(deep=True)
            else:
                rtl_type = self._adapt_data_type(data_type)
            declarator = self._object(node.get("declarator"), "port declarator")
            self._reject_declarator_extensions(declarator, category="port")
            ports.append(
                Port(
                    name=self._token_text(declarator.get("name"), "port name"),
                    direction=direction,
                    rtl_type=rtl_type,
                    driver_kind=None,
                    source_span=self._source_span,
                )
            )
            previous_direction = direction
            previous_type = rtl_type.model_copy(deep=True)
        return ports

    def _adapt_signal_declaration(self, declaration: JsonObject) -> list[Signal]:
        kind = self._kind(declaration)
        if kind == "NetDeclaration":
            net_type = declaration.get("netType")
            if (
                net_type is not None
                and self._kind(self._object(net_type, "net type")) != "WireKeyword"
            ):
                self._unsupported(
                    "只支持 wire net declaration",
                    code="HDLX-SV-NET-TYPE",
                )
        data_type = self._object(declaration.get("type"), "data type")
        rtl_type = self._adapt_data_type(data_type)
        signals: list[Signal] = []
        for declarator in self._node_list(declaration.get("declarators")):
            self._reject_declarator_extensions(declarator, category="signal")
            signals.append(
                Signal(
                    name=self._token_text(declarator.get("name"), "signal name"),
                    rtl_type=rtl_type.model_copy(deep=True),
                    driver_kind=None,
                    source_span=self._source_span,
                )
            )
        return signals

    def _adapt_data_type(
        self,
        data_type: JsonObject,
    ) -> ScalarType | VectorType | IntegerType:
        if self._kind(data_type) in {"IntType", "IntegerType"}:
            self._unsupported(
                "int/integer 数据对象不在 v0.2 MVP 内；仅参数允许 integral atom type",
                code="HDLX-SV-DATA-INTEGER",
            )
        return self._adapt_type(data_type)

    def _adapt_type(self, data_type: JsonObject) -> ScalarType | VectorType | IntegerType:
        kind = self._kind(data_type)
        if kind in {"IntType", "IntegerType"}:
            signing = data_type.get("signing")
            if (
                signing is not None
                and self._kind(self._object(signing, "integer signing"))
                == "UnsignedKeyword"
            ):
                self._unsupported(
                    "int/integer unsigned parameter 无法用 Verilog-2001 integer "
                    "保持 signed sizing",
                    code="HDLX-SV-PARAMETER-SIGNEDNESS",
                )
            if data_type.get("dimensions"):
                self._unsupported(
                    "integer packed dimension 不在 v0.2 MVP 内",
                    code="HDLX-SV-COMPLEX-TYPE",
                )
            return IntegerType(source_span=self._source_span)
        if kind == "BitType":
            self._unsupported(
                "two-state bit 无法由 Verilog-2001 four-state 变量精确保留",
                code="HDLX-SV-TWO-STATE",
            )
        if kind not in {"LogicType", "RegType", "ImplicitType"}:
            self._unsupported(
                f"data type {kind} 不在 v0.2 MVP 内",
                code="HDLX-SV-COMPLEX-TYPE",
            )

        signing = data_type.get("signing")
        signed = (
            signing is not None
            and self._kind(self._object(signing, "type signing")) == "SignedKeyword"
        )
        dimensions = [
            node
            for node in self._node_list(data_type.get("dimensions"))
            if self._kind(node) == "VariableDimension"
        ]
        if len(dimensions) > 1:
            self._unsupported(
                "只支持一维 packed vector",
                code="HDLX-SV-PACKED-DIMENSIONS",
            )
        four_state = True
        if not dimensions:
            return ScalarType(
                signed=signed,
                four_state=four_state,
                source_span=self._source_span,
            )

        specifier = self._object(dimensions[0].get("specifier"), "packed dimension")
        if self._kind(specifier) != "RangeDimensionSpecifier":
            self._unsupported(
                "packed dimension 必须使用显式 [left:right] range",
                code="HDLX-SV-PACKED-RANGE",
            )
        selector = self._object(specifier.get("selector"), "packed range selector")
        if self._kind(selector) != "SimpleRangeSelect":
            self._unsupported(
                "只支持简单 packed range",
                code="HDLX-SV-PACKED-RANGE",
            )
        left = self._adapt_expression(self._object(selector.get("left"), "range left"))
        right = self._adapt_expression(self._object(selector.get("right"), "range right"))
        direction = self._range_direction(left, right)
        return VectorType(
            range=VectorRange(
                left=left,
                right=right,
                direction=direction,
                source_span=self._source_span,
            ),
            signed=signed,
            four_state=four_state,
            source_span=self._source_span,
        )

    def _adapt_continuous_assign(
        self,
        member: JsonObject,
    ) -> list[ContinuousAssignment]:
        if member.get("delay") is not None or member.get("strength") is not None:
            self._unsupported(
                "continuous assign delay/strength 不在可综合 MVP 内",
                code="HDLX-SV-ASSIGN-CONTROL",
            )
        result: list[ContinuousAssignment] = []
        for assignment in self._node_list(member.get("assignments")):
            if self._kind(assignment) != "AssignmentExpression":
                self._unsupported(
                    "continuous assign 必须是简单赋值",
                    code="HDLX-SV-CONTINUOUS-ASSIGNMENT",
                )
            result.append(
                ContinuousAssignment(
                    target=self._adapt_expression(
                        self._object(assignment.get("left"), "assignment target")
                    ),
                    value=self._adapt_expression(
                        self._object(assignment.get("right"), "assignment value")
                    ),
                    source_span=self._source_span,
                )
            )
        return result

    def _adapt_always_comb(self, member: JsonObject) -> CombinationalProcess:
        statement = self._object(member.get("statement"), "always_comb statement")
        label = self._block_label(statement)
        body = self._adapt_statement_body(statement, process="comb")
        return CombinationalProcess(
            label=label,
            sensitivity=[],
            body=body,
            source_span=self._source_span,
        )

    def _adapt_always_ff(self, member: JsonObject) -> SequentialProcess:
        timing_statement = self._object(member.get("statement"), "always_ff statement")
        if self._kind(timing_statement) != "TimingControlStatement":
            self._unsupported(
                "always_ff 必须含单一 event control",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )
        timing = self._object(timing_statement.get("timingControl"), "event control")
        if self._kind(timing) != "EventControlWithExpression":
            self._unsupported(
                "always_ff event control 形态不受支持",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )
        events = self._adapt_events(self._object(timing.get("expr"), "event expression"))
        if len(events) not in {1, 2}:
            self._unsupported(
                "always_ff 只支持一个 clock 和可选的一个异步 reset event",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )

        body_node = self._object(timing_statement.get("statement"), "always_ff body")
        label = self._block_label(body_node)
        top_statements = self._statement_nodes(body_node)
        reset: ResetSpec | None = None
        reset_body: list[StatementNode] = []
        normal_body: list[StatementNode]

        if len(events) == 2:
            conditional = self._single_reset_conditional(top_statements)
            condition = self._condition_expression(conditional)
            reset_name, active_level = self._reset_condition(condition)
            reset_index = self._matching_reset_event(events, reset_name, active_level)
            clock_index = 1 - reset_index
            clock_edge, clock = events[clock_index]
            reset = ResetSpec(
                signal=Identifier(name=reset_name, source_span=self._source_span),
                kind=ResetKind.ASYNCHRONOUS,
                active_level=active_level,
                source_span=self._source_span,
            )
            reset_body = self._adapt_statement_body(
                self._object(conditional.get("statement"), "reset branch"),
                process="ff",
            )
            normal_body = self._adapt_required_else(conditional, process="ff")
        else:
            clock_edge, clock = events[0]
            sync = self._try_synchronous_reset(top_statements)
            if sync is None:
                normal_body = self._adapt_statement_body(body_node, process="ff")
            else:
                conditional, reset_name, active_level = sync
                reset = ResetSpec(
                    signal=Identifier(name=reset_name, source_span=self._source_span),
                    kind=ResetKind.SYNCHRONOUS,
                    active_level=active_level,
                    source_span=self._source_span,
                )
                reset_body = self._adapt_statement_body(
                    self._object(conditional.get("statement"), "reset branch"),
                    process="ff",
                )
                normal_body = self._adapt_required_else(conditional, process="ff")

        return SequentialProcess(
            label=label,
            clock=clock,
            edge=clock_edge,
            reset=reset,
            reset_body=reset_body,
            body=normal_body,
            source_span=self._source_span,
        )

    def _adapt_events(self, expression: JsonObject) -> list[tuple[EdgeKind, Identifier]]:
        kind = self._kind(expression)
        if kind == "ParenthesizedEventExpression":
            return self._adapt_events(self._object(expression.get("expr"), "event expression"))
        if kind == "BinaryEventExpression":
            operator = self._object(expression.get("operatorToken"), "event operator")
            if self._kind(operator) != "OrKeyword":
                self._unsupported(
                    "always_ff 事件只能用 or 连接",
                    code="HDLX-SV-ALWAYS-FF-EVENT",
                )
            return [
                *self._adapt_events(self._object(expression.get("left"), "left event")),
                *self._adapt_events(self._object(expression.get("right"), "right event")),
            ]
        if kind != "SignalEventExpression":
            self._unsupported(
                "always_ff 只支持 posedge/negedge identifier",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )
        edge_node = self._object(expression.get("edge"), "event edge")
        edge_kind = self._kind(edge_node)
        if edge_kind == "PosEdgeKeyword":
            edge = EdgeKind.POSITIVE
        elif edge_kind == "NegEdgeKeyword":
            edge = EdgeKind.NEGATIVE
        else:
            self._unsupported(
                "always_ff event 缺少 posedge/negedge",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )
        value = self._adapt_expression(self._object(expression.get("expr"), "event signal"))
        if not isinstance(value, Identifier):
            self._unsupported(
                "always_ff edge signal 必须是直接 identifier",
                code="HDLX-SV-ALWAYS-FF-EVENT",
            )
        return [(edge, value)]

    def _single_reset_conditional(self, statements: list[JsonObject]) -> JsonObject:
        if len(statements) != 1 or self._kind(statements[0]) != "ConditionalStatement":
            self._unsupported(
                "异步 reset always_ff 必须由顶层 if(reset) / else 构成",
                code="HDLX-SV-ASYNC-RESET-SHAPE",
            )
        return statements[0]

    def _matching_reset_event(
        self,
        events: list[tuple[EdgeKind, Identifier]],
        reset_name: str,
        active_level: ActiveLevel,
    ) -> int:
        expected_edge = EdgeKind.POSITIVE if active_level is ActiveLevel.HIGH else EdgeKind.NEGATIVE
        matches = [
            index
            for index, (edge, signal) in enumerate(events)
            if signal.name == reset_name and edge is expected_edge
        ]
        if len(matches) != 1:
            self._unsupported(
                "异步 reset 条件与 event control 的信号/有效边沿不一致",
                code="HDLX-SV-ASYNC-RESET-EVENT",
            )
        return matches[0]

    def _try_synchronous_reset(
        self,
        statements: list[JsonObject],
    ) -> tuple[JsonObject, str, ActiveLevel] | None:
        if len(statements) != 1 or self._kind(statements[0]) != "ConditionalStatement":
            return None
        conditional = statements[0]
        condition = self._condition_expression(conditional)
        try:
            reset_name, active_level = self._reset_condition(condition)
        except UnsupportedConstructError:
            return None
        if not self._looks_like_reset_name(reset_name):
            return None
        if conditional.get("elseClause") is None:
            return None
        return conditional, reset_name, active_level

    @staticmethod
    def _looks_like_reset_name(name: str) -> bool:
        folded = name.casefold()
        return (
            folded in {"rst", "reset", "rst_n", "reset_n"}
            or folded.startswith("rst_")
            or folded.startswith("reset_")
            or folded.endswith("_rst")
            or folded.endswith("_reset")
            or folded.endswith("_rst_n")
            or folded.endswith("_reset_n")
        )

    def _reset_condition(self, condition: ExpressionNode) -> tuple[str, ActiveLevel]:
        if isinstance(condition, Identifier):
            return condition.name, ActiveLevel.HIGH
        if (
            isinstance(condition, UnaryExpr)
            and condition.operator is UnaryOperator.LOGICAL_NOT
            and isinstance(condition.operand, Identifier)
        ):
            return condition.operand.name, ActiveLevel.LOW
        self._unsupported(
            "reset 条件只支持 reset 或 !reset",
            code="HDLX-SV-RESET-CONDITION",
        )

    def _adapt_required_else(
        self,
        conditional: JsonObject,
        *,
        process: str,
    ) -> list[StatementNode]:
        else_clause = conditional.get("elseClause")
        if else_clause is None:
            self._unsupported(
                "reset 分支必须含 else 正常工作分支",
                code="HDLX-SV-RESET-ELSE",
            )
        clause = self._object(else_clause, "else clause")
        return self._adapt_statement_body(
            self._object(clause.get("clause"), "else statement"),
            process=process,
        )

    def _adapt_statement_body(
        self,
        statement: JsonObject,
        *,
        process: str,
    ) -> list[StatementNode]:
        return [
            self._adapt_statement(node, process=process)
            for node in self._statement_nodes(statement)
        ]

    def _statement_nodes(self, statement: JsonObject) -> list[JsonObject]:
        if self._kind(statement) == "SequentialBlockStatement":
            return self._node_list(statement.get("items"))
        return [statement]

    def _adapt_statement(self, statement: JsonObject, *, process: str) -> StatementNode:
        kind = self._kind(statement)
        if kind == "ExpressionStatement":
            expression = self._object(statement.get("expr"), "statement expression")
            assignment_kind = self._kind(expression)
            if process == "comb" and assignment_kind != "AssignmentExpression":
                self._unsupported(
                    "always_comb 只支持 blocking assignment",
                    code="HDLX-SV-COMB-ASSIGNMENT",
                )
            if process == "ff" and assignment_kind != "NonblockingAssignmentExpression":
                self._unsupported(
                    "always_ff 只支持 nonblocking assignment",
                    code="HDLX-SV-FF-ASSIGNMENT",
                )
            return ProceduralAssignment(
                target=self._adapt_expression(
                    self._object(expression.get("left"), "assignment target")
                ),
                value=self._adapt_expression(
                    self._object(expression.get("right"), "assignment value")
                ),
                assignment_kind=(
                    AssignmentKind.BLOCKING if process == "comb" else AssignmentKind.NON_BLOCKING
                ),
                source_span=self._source_span,
            )
        if kind == "ConditionalStatement":
            condition = self._condition_expression(statement)
            then_body = self._adapt_statement_body(
                self._object(statement.get("statement"), "if statement"),
                process=process,
            )
            else_body: list[StatementNode] = []
            if statement.get("elseClause") is not None:
                else_clause = self._object(statement.get("elseClause"), "else clause")
                else_body = self._adapt_statement_body(
                    self._object(else_clause.get("clause"), "else statement"),
                    process=process,
                )
            return IfStatement(
                condition=condition,
                then_body=then_body,
                else_body=else_body,
                source_span=self._source_span,
            )
        if kind == "CaseStatement":
            if (
                self._kind(self._object(statement.get("caseKeyword"), "case keyword"))
                != "CaseKeyword"
            ):
                self._unsupported(
                    "只支持精确 case，不支持 casex/casez",
                    code="HDLX-SV-CASE-KIND",
                )
            alternatives: list[CaseAlternative] = []
            default_body: list[StatementNode] = []
            for item in self._node_list(statement.get("items")):
                item_kind = self._kind(item)
                clause = self._object(item.get("clause"), "case clause")
                body = self._adapt_statement_body(clause, process=process)
                if item_kind == "DefaultCaseItem":
                    if default_body:
                        self._unsupported(
                            "case 只能包含一个 default",
                            code="HDLX-SV-CASE-DEFAULT",
                        )
                    default_body = body
                elif item_kind == "StandardCaseItem":
                    selectors = [
                        self._adapt_expression(expression)
                        for expression in self._node_list(item.get("expressions"))
                    ]
                    alternatives.append(
                        CaseAlternative(
                            selectors=selectors,
                            body=body,
                            source_span=self._source_span,
                        )
                    )
                else:
                    self._unsupported(
                        f"case item {item_kind} 不受支持",
                        code="HDLX-SV-CASE-ITEM",
                    )
            return CaseStatement(
                expression=self._adapt_expression(
                    self._object(statement.get("expr"), "case expression")
                ),
                alternatives=alternatives,
                default_body=default_body,
                source_span=self._source_span,
            )
        if kind == "EmptyStatement":
            return NullStatement(source_span=self._source_span)
        self._unsupported(
            f"procedural statement {kind} 不在 v0.2 MVP 内",
            code="HDLX-SV-STATEMENT",
        )

    def _condition_expression(self, statement: JsonObject) -> ExpressionNode:
        predicate = self._object(statement.get("predicate"), "conditional predicate")
        conditions = self._node_list(predicate.get("conditions"))
        if len(conditions) != 1 or self._kind(conditions[0]) != "ConditionalPattern":
            self._unsupported(
                "if 条件只支持单一 integral expression",
                code="HDLX-SV-CONDITION",
            )
        return self._adapt_expression(
            self._object(conditions[0].get("expr"), "condition expression")
        )

    def _adapt_instances(self, member: JsonObject) -> list[Instance]:
        referenced_unit = self._token_text(member.get("type"), "instance module name")
        parameter_bindings: list[ParameterBinding] = []
        parameter_values = member.get("parameters")
        if parameter_values is not None:
            container = self._object(parameter_values, "parameter value assignment")
            for position, binding in enumerate(self._node_list(container.get("parameters"))):
                kind = self._kind(binding)
                if kind == "NamedParamAssignment":
                    parameter_bindings.append(
                        ParameterBinding(
                            formal=self._token_text(binding.get("name"), "parameter formal"),
                            value=self._adapt_expression(
                                self._object(binding.get("expr"), "parameter value")
                            ),
                            source_span=self._source_span,
                        )
                    )
                elif kind == "OrderedParamAssignment":
                    parameter_bindings.append(
                        ParameterBinding(
                            position=position,
                            value=self._adapt_expression(
                                self._object(binding.get("expr"), "parameter value")
                            ),
                            source_span=self._source_span,
                        )
                    )
                else:
                    self._unsupported(
                        f"parameter connection {kind} 不受支持",
                        code="HDLX-SV-PARAMETER-CONNECTION",
                    )

        instances: list[Instance] = []
        for instance_node in self._node_list(member.get("instances")):
            if self._kind(instance_node) != "HierarchicalInstance":
                self._unsupported(
                    "只支持普通 module instance",
                    code="HDLX-SV-INSTANCE-KIND",
                )
            declaration = self._object(instance_node.get("decl"), "instance declaration")
            if declaration.get("dimensions"):
                self._unsupported(
                    "instance array 不在 v0.2 MVP 内",
                    code="HDLX-SV-INSTANCE-ARRAY",
                )
            port_bindings: list[PortBinding] = []
            for position, binding in enumerate(self._node_list(instance_node.get("connections"))):
                kind = self._kind(binding)
                if kind == "NamedPortConnection":
                    value = self._connection_expression(binding.get("expr"))
                    port_bindings.append(
                        PortBinding(
                            formal=self._token_text(binding.get("name"), "port formal"),
                            value=value,
                            source_span=self._source_span,
                        )
                    )
                elif kind == "OrderedPortConnection":
                    port_bindings.append(
                        PortBinding(
                            position=position,
                            value=self._connection_expression(binding.get("expr")),
                            source_span=self._source_span,
                        )
                    )
                else:
                    self._unsupported(
                        "implicit/wildcard port connection 不在 v0.2 MVP 内",
                        code="HDLX-SV-PORT-CONNECTION",
                    )
            instances.append(
                Instance(
                    referenced_unit=referenced_unit,
                    name=self._token_text(declaration.get("name"), "instance name"),
                    parameter_bindings=[
                        binding.model_copy(deep=True) for binding in parameter_bindings
                    ],
                    port_bindings=port_bindings,
                    source_span=self._source_span,
                )
            )
        return instances

    def _connection_expression(self, value: object) -> ExpressionNode | None:
        if value is None:
            return None
        return self._adapt_expression(self._object(value, "connection expression"))

    def _adapt_expression(self, expression: JsonObject) -> ExpressionNode:
        kind = self._kind(expression)
        if kind in {"SimplePropertyExpr", "SimpleSequenceExpr", "ParenthesizedExpression"}:
            nested = expression.get("expr") or expression.get("expression")
            return self._adapt_expression(self._object(nested, "wrapped expression"))
        if kind == "IdentifierName":
            name = self._token_text(expression.get("identifier"), "identifier")
            local = self._localparams.get(name)
            if local is not None:
                return local.model_copy(deep=True)
            return Identifier(name=name, source_span=self._source_span)
        if kind == "IdentifierSelectName":
            value: ExpressionNode = Identifier(
                name=self._token_text(expression.get("identifier"), "identifier"),
                source_span=self._source_span,
            )
            local = self._localparams.get(value.name)
            if local is not None:
                value = local.model_copy(deep=True)
            for selector_node in self._node_list(expression.get("selectors")):
                if self._kind(selector_node) != "ElementSelect":
                    self._unsupported(
                        "只支持一维 index/slice selector",
                        code="HDLX-SV-SELECTOR",
                    )
                selector = self._object(selector_node.get("selector"), "selector")
                if self._kind(selector) == "SimpleRangeSelect":
                    left = self._adapt_expression(self._object(selector.get("left"), "slice left"))
                    right = self._adapt_expression(
                        self._object(selector.get("right"), "slice right")
                    )
                    value = Slice(
                        value=value,
                        left=left,
                        right=right,
                        direction=self._range_direction(left, right),
                        source_span=self._source_span,
                    )
                else:
                    value = Index(
                        value=value,
                        index=self._adapt_expression(selector),
                        source_span=self._source_span,
                    )
            return value
        if kind == "IntegerLiteralExpression":
            text = self._token_text(expression.get("literal"), "integer literal")
            try:
                value = int(text.replace("_", ""), 10)
            except ValueError as error:
                raise UnsupportedConstructError(
                    f"无法解析 integer literal {text!r}",
                    code="HDLX-SV-LITERAL",
                    source_span=self._source_span,
                ) from error
            return Literal(
                value=value,
                literal_kind=LiteralKind.INTEGER,
                source_span=self._source_span,
            )
        if kind == "IntegerVectorExpression":
            return self._adapt_vector_literal(expression)
        if kind == "UnbasedUnsizedLiteralExpression":
            text = self._token_text(expression.get("literal"), "unbased literal").casefold()
            if text != "'0":
                self._unsupported(
                    f"unbased unsized literal {text!r} 无法安全降为 Verilog-2001",
                    code="HDLX-SV-UNBASED-LITERAL",
                )
            return Literal(
                value=0,
                literal_kind=LiteralKind.INTEGER,
                source_span=self._source_span,
            )
        if kind in _UNARY_OPERATORS:
            return UnaryExpr(
                operator=_UNARY_OPERATORS[kind],
                operand=self._adapt_expression(
                    self._object(expression.get("operand"), "unary operand")
                ),
                source_span=self._source_span,
            )
        if kind in _BINARY_OPERATORS:
            left = self._adapt_expression(self._object(expression.get("left"), "binary left"))
            right = self._adapt_expression(
                self._object(expression.get("right"), "binary right")
            )
            left_signed = self._declared_signedness(left)
            right_signed = self._declared_signedness(right)
            if (
                left_signed is not None
                and right_signed is not None
                and left_signed != right_signed
            ):
                self._unsupported(
                    "mixed signed/unsigned binary expression 的 sizing 无法保证 Verilog-2001 等价",
                    code="HDLX-SV-SIGNED-SIZING",
                )
            return BinaryExpr(
                left=left,
                operator=_BINARY_OPERATORS[kind],
                right=right,
                source_span=self._source_span,
            )
        if kind == "ConditionalExpression":
            predicate = self._object(expression.get("predicate"), "ternary predicate")
            conditions = self._node_list(predicate.get("conditions"))
            if len(conditions) != 1 or self._kind(conditions[0]) != "ConditionalPattern":
                self._unsupported(
                    "ternary predicate 只支持单一 expression",
                    code="HDLX-SV-TERNARY-PREDICATE",
                )
            return TernaryExpr(
                condition=self._adapt_expression(
                    self._object(conditions[0].get("expr"), "ternary condition")
                ),
                when_true=self._adapt_expression(
                    self._object(expression.get("left"), "ternary true expression")
                ),
                when_false=self._adapt_expression(
                    self._object(expression.get("right"), "ternary false expression")
                ),
                source_span=self._source_span,
            )
        if kind == "ConcatenationExpression":
            return Concatenation(
                parts=[
                    self._adapt_expression(node)
                    for node in self._node_list(expression.get("expressions"))
                ],
                source_span=self._source_span,
            )
        self._unsupported(
            f"expression {kind} 不在 v0.2 MVP 内",
            code="HDLX-SV-EXPRESSION",
        )

    def _adapt_vector_literal(self, expression: JsonObject) -> Literal:
        if expression.get("signing") is not None:
            self._unsupported(
                "signed based literal 暂不支持",
                code="HDLX-SV-LITERAL-SIGNED",
            )
        size_text = self._token_text(expression.get("size"), "literal size")
        try:
            width = int(size_text.replace("_", ""), 10)
        except ValueError as error:
            raise UnsupportedConstructError(
                f"literal size {size_text!r} 不是常量整数",
                code="HDLX-SV-LITERAL-WIDTH",
                source_span=self._source_span,
            ) from error
        base = self._token_text(expression.get("base"), "literal base").casefold()
        digits = self._token_text(expression.get("value"), "literal value").replace("_", "")
        bits = self._digits_to_bits(base, digits)
        if len(bits) < width:
            bits = bits.rjust(width, "0")
        elif len(bits) > width:
            bits = bits[-width:]
        return Literal(
            value=bits,
            literal_kind=LiteralKind.BIT_VECTOR,
            bit_width=width,
            signed=False,
            source_span=self._source_span,
        )

    def _digits_to_bits(self, base: str, digits: str) -> str:
        if base == "'b":
            bits = digits
        elif base == "'o":
            bits = "".join(self._expand_based_digit(character, 3) for character in digits)
        elif base == "'h":
            bits = "".join(self._expand_based_digit(character, 4) for character in digits)
        elif base == "'d" and all(character.isdigit() for character in digits):
            bits = format(int(digits, 10), "b")
        else:
            self._unsupported(
                f"based literal {base}{digits} 不受支持",
                code="HDLX-SV-LITERAL-BASE",
            )
        if not bits or any(character not in "01xXzZ" for character in bits):
            self._unsupported(
                f"literal {base}{digits} 含不支持的逻辑值",
                code="HDLX-SV-LITERAL-VALUE",
            )
        return bits.lower()

    def _expand_based_digit(self, character: str, width: int) -> str:
        if character in "xXzZ":
            return character.lower() * width
        try:
            return format(int(character, 16), f"0{width}b")
        except ValueError:
            self._unsupported(
                f"based literal digit {character!r} 不受支持",
                code="HDLX-SV-LITERAL-VALUE",
            )

    @staticmethod
    def _range_direction(left: ExpressionNode, right: ExpressionNode) -> RangeDirection:
        left_value = left.value if isinstance(left, Literal) and type(left.value) is int else None
        right_value = (
            right.value if isinstance(right, Literal) and type(right.value) is int else None
        )
        if left_value is not None and right_value is not None:
            return (
                RangeDirection.ASCENDING if left_value <= right_value else RangeDirection.DESCENDING
            )
        if left_value == 0 and right_value is None:
            return RangeDirection.ASCENDING
        return RangeDirection.DESCENDING

    @staticmethod
    def _adapt_direction(node: JsonObject) -> PortDirection:
        kind = SystemVerilogAdapter._kind(node)
        mapping = {
            "InputKeyword": PortDirection.INPUT,
            "OutputKeyword": PortDirection.OUTPUT,
            "InOutKeyword": PortDirection.INOUT,
        }
        if kind not in mapping:
            raise UnsupportedConstructError(
                f"port direction {kind} 不受支持",
                code="HDLX-SV-PORT-DIRECTION",
            )
        return mapping[kind]

    def _reject_declarator_extensions(self, declarator: JsonObject, *, category: str) -> None:
        if declarator.get("initializer") is not None:
            self._unsupported(
                f"{category} initializer 无法保证 Verilog-2001 初态等价",
                code="HDLX-SV-INITIALIZER",
            )
        if declarator.get("dimensions"):
            self._unsupported(
                f"{category} unpacked array 不在 v0.2 MVP 内",
                code="HDLX-SV-UNPACKED-ARRAY",
            )

    def _block_label(self, statement: JsonObject) -> str | None:
        if self._kind(statement) != "SequentialBlockStatement":
            return None
        block_name = statement.get("blockName")
        if block_name is None:
            return None
        clause = self._object(block_name, "block name")
        return self._token_text(clause.get("name"), "block label")

    @staticmethod
    def _span(raw: RawSourceSpan) -> SourceSpan:
        return SourceSpan(
            start=SourceLocation(
                file=str(raw.file),
                line=raw.start_line,
                column=raw.start_column,
            ),
            end=SourceLocation(
                file=str(raw.file),
                line=raw.end_line,
                column=raw.end_column,
            ),
        )

    @staticmethod
    def _node_list(value: object) -> list[JsonObject]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("Slang serialized syntax list must be a list")
        return [item for item in value if isinstance(item, dict) and "text" not in item]

    @staticmethod
    def _object(value: object, description: str) -> JsonObject:
        if not isinstance(value, dict):
            raise UnsupportedConstructError(
                f"Slang serialization 缺少 {description}",
                code="HDLX-SV-SERIALIZATION",
            )
        return value

    @staticmethod
    def _kind(node: Mapping[str, object]) -> str:
        kind = node.get("kind")
        if not isinstance(kind, str):
            raise UnsupportedConstructError(
                "Slang serialization node 缺少 kind",
                code="HDLX-SV-SERIALIZATION",
            )
        return kind

    @classmethod
    def _expect_kind(cls, node: Mapping[str, object], expected: str) -> None:
        actual = cls._kind(node)
        if actual != expected:
            raise UnsupportedConstructError(
                f"期望 {expected}，实际为 {actual}",
                code="HDLX-SV-SERIALIZATION",
            )

    @classmethod
    def _token_text(cls, value: object, description: str) -> str:
        node = cls._object(value, description)
        text = node.get("text")
        if not isinstance(text, str) or not text:
            raise UnsupportedConstructError(
                f"Slang token 缺少 {description}",
                code="HDLX-SV-SERIALIZATION",
            )
        return text

    def _unsupported(self, message: str, *, code: str) -> None:
        raise UnsupportedConstructError(
            message,
            code=code,
            source_span=self._source_span,
        )

    @staticmethod
    def _contains_any_identifier(
        expression: ExpressionNode,
        names: set[str],
    ) -> bool:
        if isinstance(expression, Identifier):
            return expression.name in names
        children: Iterable[ExpressionNode]
        if isinstance(expression, UnaryExpr):
            children = (expression.operand,)
        elif isinstance(expression, BinaryExpr):
            children = (expression.left, expression.right)
        elif isinstance(expression, TernaryExpr):
            children = (
                expression.condition,
                expression.when_true,
                expression.when_false,
            )
        elif isinstance(expression, Concatenation):
            children = expression.parts
        elif isinstance(expression, Index):
            children = (expression.value, expression.index)
        elif isinstance(expression, Slice):
            children = (expression.value, expression.left, expression.right)
        else:
            return False
        return any(
            SystemVerilogAdapter._contains_any_identifier(child, names) for child in children
        )

    def _declared_signedness(self, expression: ExpressionNode) -> bool | None:
        while isinstance(expression, Index | Slice):
            expression = expression.value
        if not isinstance(expression, Identifier):
            return None
        rtl_type = self._declared_types.get(expression.name)
        return None if rtl_type is None else rtl_type.signed


__all__ = ["SystemVerilogAdapter"]
