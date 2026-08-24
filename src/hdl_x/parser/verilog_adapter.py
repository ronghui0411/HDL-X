"""Verilog-2001 Raw Slang syntax 到 Canonical IR 的适配入口。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from hdl_x.diagnostics import HDLXError
from hdl_x.ir import (
    BinaryExpr,
    BinaryOperator,
    CombinationalProcess,
    Design,
    EdgeKind,
    ForGenerate,
    Identifier,
    IfGenerate,
    IntegerType,
    Literal,
    LiteralKind,
    Module,
    ModuleItem,
    RangeDirection,
    ScalarType,
    SequentialProcess,
    SourceLocation,
    SourceSpan,
    VectorRange,
    VectorType,
)
from hdl_x.parser.base import ParserAdapter
from hdl_x.parser.slang import (
    RawSystemVerilogDesign,
    RawSystemVerilogModule,
)
from hdl_x.parser.systemverilog_adapter import SystemVerilogAdapter

JsonObject = dict[str, Any]

_SOURCE_SPAN_KEY = "_hdl_x_source_span"

_CODE_OVERRIDES = {
    "HDLX-SV-FF-ASSIGNMENT": "HDLX-V2V-SEQUENTIAL-BLOCKING",
    "HDLX-SV-COMB-ASSIGNMENT": "HDLX-V2V-COMBINATIONAL-NONBLOCKING",
}


class VerilogAdapter(SystemVerilogAdapter, ParserAdapter[RawSystemVerilogDesign]):
    """复用共享 integral 适配，并增加普通 Verilog ``always`` 语义。"""

    def adapt(self, representation: RawSystemVerilogDesign) -> Design:
        try:
            return super().adapt(representation)
        except HDLXError as error:
            diagnostic = error.diagnostic
            code = _CODE_OVERRIDES.get(diagnostic.code, diagnostic.code)
            if code.startswith("HDLX-SV-"):
                code = f"HDLX-V2V-{code.removeprefix('HDLX-SV-')}"
            message = (
                diagnostic.message.replace("SystemVerilog", "Verilog-2001")
                .replace("always_ff", "edge-triggered always")
                .replace("always_comb", "combinational always")
                .replace("v0.2", "v0.3")
            )
            raise type(error)(
                diagnostic=diagnostic.model_copy(update={"code": code, "message": message})
            ) from error

    def _adapt_module(self, raw: RawSystemVerilogModule) -> Module:
        self._source_span = self._span(raw.source)
        self._localparams = {}
        self._declared_types = {}
        self._genvar_names: set[str] = set()
        payload = raw.syntax
        self._expect_kind(payload, "ModuleDeclaration")
        header = self._object(payload.get("header"), "module header")
        self._all_localparam_names = self._collect_localparam_names(header, payload)

        parameters = []
        for declaration in self._parameter_declarations(header.get("parameters")):
            start = len(parameters)
            self._adapt_parameter_declaration(declaration, parameters)
            if len(parameters) > start:
                self._assign_source_spans(
                    parameters[start:],
                    self._node_list(declaration.get("declarators")),
                )

        ports = self._adapt_ports(header.get("ports"))
        if header.get("ports") is not None:
            port_list = self._object(header.get("ports"), "ANSI port list")
            self._assign_source_spans(ports, self._node_list(port_list.get("ports")))
        self._declared_types.update({port.name: port.rtl_type for port in ports})
        signals = []
        items: list[ModuleItem] = []
        for member in self._node_list(payload.get("members")):
            kind = self._kind(member)
            if kind == "GenvarDeclaration":
                self._adapt_genvar_declaration(member)
            elif kind == "GenerateRegion":
                items.extend(self._adapt_generate_region(member))
            elif kind == "LoopGenerate":
                items.append(self._adapt_loop_generate(member))
            elif kind == "IfGenerate":
                items.append(self._adapt_if_generate(member))
            elif kind == "ParameterDeclaration":
                start = len(parameters)
                self._adapt_parameter_declaration(member, parameters)
                if len(parameters) > start:
                    self._assign_source_spans(
                        parameters[start:],
                        self._node_list(member.get("declarators")),
                    )
            elif kind in {"DataDeclaration", "NetDeclaration"}:
                declarations = self._adapt_signal_declaration(member)
                self._assign_source_spans(
                    declarations,
                    self._node_list(member.get("declarators")),
                )
                signals.extend(declarations)
                self._declared_types.update(
                    {item.name: item.rtl_type for item in declarations}
                )
            elif kind == "ContinuousAssign":
                assignments = self._adapt_continuous_assign(member)
                self._assign_source_spans(
                    assignments,
                    self._node_list(member.get("assignments")),
                )
                items.extend(assignments)
            elif kind == "AlwaysBlock":
                items.append(self._adapt_always(member))
            elif kind == "HierarchyInstantiation":
                instances = self._adapt_instances(member)
                self._assign_source_spans(
                    instances,
                    self._node_list(member.get("instances")),
                )
                items.extend(instances)
            else:
                self._unsupported(
                    f"module member {kind} 不在 Verilog-2001 v0.3 MVP 内",
                    code="HDLX-V2V-MODULE-MEMBER",
                )

        for parameter in parameters:
            if (
                isinstance(parameter.rtl_type, ScalarType)
                and isinstance(parameter.default, Literal)
                and parameter.default.literal_kind is LiteralKind.INTEGER
            ):
                parameter.rtl_type = IntegerType(source_span=parameter.rtl_type.source_span)

        return Module(
            name=raw.name,
            parameters=parameters,
            ports=ports,
            signals=signals,
            items=items,
            source_span=self._source_span,
        )

    def _adapt_genvar_declaration(self, member: JsonObject) -> None:
        with self._using_node_span(member):
            identifiers = self._node_list(member.get("identifiers"))
            if not identifiers:
                self._unsupported(
                    "genvar declaration 必须声明 identifier",
                    code="HDLX-V2V-GENVAR",
                )
            for identifier in identifiers:
                self._expect_kind(identifier, "IdentifierName")
                self._genvar_names.add(
                    self._token_text(identifier.get("identifier"), "genvar name")
                )

    def _adapt_generate_region(self, member: JsonObject) -> list[ModuleItem]:
        with self._using_node_span(member):
            result: list[ModuleItem] = []
            for generate in self._node_list(member.get("members")):
                kind = self._kind(generate)
                if kind == "LoopGenerate":
                    result.append(self._adapt_loop_generate(generate))
                elif kind == "IfGenerate":
                    result.append(self._adapt_if_generate(generate))
                else:
                    self._unsupported(
                        f"generate member {kind} 不在 v0.3 MVP 内",
                        code="HDLX-V2V-GENERATE-KIND",
                    )
            return result

    def _adapt_loop_generate(self, member: JsonObject) -> ForGenerate:
        with self._using_node_span(member):
            index_name = self._token_text(member.get("identifier"), "generate index")
            if index_name not in self._genvar_names:
                self._unsupported(
                    f"generate index {index_name!r} 必须由 module-scope genvar 声明",
                    code="HDLX-V2V-GENVAR",
                )
            start = self._adapt_expression(
                self._object(member.get("initialExpr"), "generate initial expression")
            )
            vector_range = self._adapt_generate_range(
                member,
                index_name=index_name,
                start=start,
            )
            if self._contains_any_identifier(
                start,
                set(self._declared_types),
            ) or self._contains_any_identifier(
                vector_range.right,
                set(self._declared_types),
            ):
                self._unsupported(
                    "generate range 必须只依赖 parameter/localparam 常量",
                    code="HDLX-V2V-GENERATE-CONSTANT",
                )
            block = self._object(member.get("block"), "generate block")
            return ForGenerate(
                label=self._generate_block_label(block),
                index_name=index_name,
                range=vector_range,
                body=self._adapt_generate_block(block),
                source_span=self._source_span,
            )

    def _adapt_generate_range(
        self,
        member: JsonObject,
        *,
        index_name: str,
        start: object,
    ) -> VectorRange:
        stop = self._object(member.get("stopExpr"), "generate stop expression")
        stop_kind = self._kind(stop)
        modes = {
            "LessThanExpression": (RangeDirection.ASCENDING, True),
            "LessThanEqualExpression": (RangeDirection.ASCENDING, False),
            "GreaterThanExpression": (RangeDirection.DESCENDING, True),
            "GreaterThanEqualExpression": (RangeDirection.DESCENDING, False),
        }
        if stop_kind not in modes:
            self._unsupported(
                "generate stop condition 只支持 i <, <=, >, >= constant expression",
                code="HDLX-V2V-GENERATE-RANGE",
            )
        self._expect_generate_index(
            self._object(stop.get("left"), "generate stop index"),
            index_name,
        )
        stop_value = self._adapt_expression(
            self._object(stop.get("right"), "generate stop bound")
        )
        direction, exclusive = modes[stop_kind]
        iteration = self._object(
            member.get("iterationExpr"),
            "generate iteration expression",
        )
        self._expect_kind(iteration, "AssignmentExpression")
        self._expect_generate_index(
            self._object(iteration.get("left"), "generate iteration target"),
            index_name,
        )
        update = self._object(iteration.get("right"), "generate iteration value")
        expected_update = (
            "AddExpression"
            if direction is RangeDirection.ASCENDING
            else "SubtractExpression"
        )
        if self._kind(update) != expected_update:
            self._unsupported(
                "generate iteration 必须与 range 方向一致并使用 i = i +/- 1",
                code="HDLX-V2V-GENERATE-STEP",
            )
        self._expect_generate_index(
            self._object(update.get("left"), "generate iteration index"),
            index_name,
        )
        step = self._adapt_expression(
            self._object(update.get("right"), "generate iteration step")
        )
        if not (
            isinstance(step, Literal)
            and step.literal_kind is LiteralKind.INTEGER
            and step.value == 1
        ):
            self._unsupported(
                "generate iteration step 只支持常量 1",
                code="HDLX-V2V-GENERATE-STEP",
            )
        end = (
            self._offset_bound(
                stop_value,
                -1 if direction is RangeDirection.ASCENDING else 1,
            )
            if exclusive
            else stop_value
        )
        return VectorRange(
            left=start,
            right=end,
            direction=direction,
            source_span=self._source_span,
        )

    def _adapt_if_generate(self, member: JsonObject) -> IfGenerate:
        with self._using_node_span(member):
            if member.get("elseClause") is not None:
                self._unsupported(
                    "Verilog if-generate 的独立 else block label 无法由现有兼容 IR "
                    "无损表达；v0.3 MVP 明确拒绝",
                    code="HDLX-V2V-GENERATE-ELSE-HIERARCHY",
                )
            condition = self._adapt_expression(
                self._object(member.get("condition"), "generate condition")
            )
            if self._contains_any_identifier(condition, set(self._declared_types)):
                self._unsupported(
                    "if-generate condition 必须只依赖 parameter/localparam 常量",
                    code="HDLX-V2V-GENERATE-CONSTANT",
                )
            block = self._object(member.get("block"), "generate block")
            return IfGenerate(
                label=self._generate_block_label(block),
                condition=condition,
                then_body=self._adapt_generate_block(block),
                else_body=[],
                source_span=self._source_span,
            )

    def _adapt_generate_block(self, block: JsonObject) -> list[ModuleItem]:
        self._expect_kind(block, "GenerateBlock")
        previous_types = dict(self._declared_types)
        result: list[ModuleItem] = []
        try:
            for member in self._node_list(block.get("members")):
                kind = self._kind(member)
                if kind in {"DataDeclaration", "NetDeclaration"}:
                    declarations = self._adapt_signal_declaration(member)
                    self._assign_source_spans(
                        declarations,
                        self._node_list(member.get("declarators")),
                    )
                    result.extend(declarations)
                    self._declared_types.update(
                        {item.name: item.rtl_type for item in declarations}
                    )
                elif kind == "ContinuousAssign":
                    assignments = self._adapt_continuous_assign(member)
                    self._assign_source_spans(
                        assignments,
                        self._node_list(member.get("assignments")),
                    )
                    result.extend(assignments)
                elif kind == "HierarchyInstantiation":
                    instances = self._adapt_instances(member)
                    self._assign_source_spans(
                        instances,
                        self._node_list(member.get("instances")),
                    )
                    result.extend(instances)
                elif kind == "AlwaysBlock":
                    result.append(self._adapt_always(member))
                elif kind == "LoopGenerate":
                    result.append(self._adapt_loop_generate(member))
                elif kind == "IfGenerate":
                    result.append(self._adapt_if_generate(member))
                else:
                    self._unsupported(
                        f"generate block member {kind} 不在 v0.3 MVP 内",
                        code="HDLX-V2V-GENERATE-MEMBER",
                    )
        finally:
            self._declared_types = previous_types
        return result

    def _generate_block_label(self, block: JsonObject) -> str:
        begin_name = block.get("beginName")
        if begin_name is None:
            self._unsupported(
                "generate block 必须有显式 label 才能稳定保留层次",
                code="HDLX-V2V-GENERATE-LABEL",
            )
        clause = self._object(begin_name, "generate block name")
        return self._token_text(clause.get("name"), "generate block label")

    def _expect_generate_index(self, expression: JsonObject, expected: str) -> None:
        self._expect_kind(expression, "IdentifierName")
        actual = self._token_text(expression.get("identifier"), "generate index")
        if actual != expected:
            self._unsupported(
                "generate condition/iteration 必须引用同一 genvar",
                code="HDLX-V2V-GENERATE-INDEX",
            )

    def _offset_bound(self, expression: object, offset: int) -> object:
        if (
            isinstance(expression, Literal)
            and expression.literal_kind is LiteralKind.INTEGER
            and type(expression.value) is int
        ):
            return expression.model_copy(update={"value": expression.value + offset})
        return BinaryExpr(
            left=expression,
            operator=(
                BinaryOperator.ADD if offset > 0 else BinaryOperator.SUBTRACT
            ),
            right=Literal(
                value=abs(offset),
                literal_kind=LiteralKind.INTEGER,
                source_span=self._source_span,
            ),
            source_span=self._source_span,
        )

    def _adapt_always(
        self,
        member: JsonObject,
    ) -> CombinationalProcess | SequentialProcess:
        with self._using_node_span(member):
            return self._adapt_always_node(member)

    def _adapt_always_node(
        self,
        member: JsonObject,
    ) -> CombinationalProcess | SequentialProcess:
        timing_statement = self._object(member.get("statement"), "always statement")
        if self._kind(timing_statement) != "TimingControlStatement":
            self._unsupported(
                "ordinary always 必须含显式 event control",
                code="HDLX-V2V-ALWAYS-EVENT",
            )
        timing = self._object(timing_statement.get("timingControl"), "event control")
        body_node = self._object(timing_statement.get("statement"), "always body")
        timing_kind = self._kind(timing)
        if timing_kind == "ImplicitEventControl":
            return self._combinational_process(body_node, sensitivity=[])
        if timing_kind != "EventControlWithExpression":
            self._unsupported(
                f"event control {timing_kind} 不在 v0.3 MVP 内",
                code="HDLX-V2V-ALWAYS-EVENT",
            )

        events = self._adapt_event_modes(
            self._object(timing.get("expr"), "event expression")
        )
        edge_modes = [edge for edge, _signal in events]
        if all(edge is None for edge in edge_modes):
            return self._combinational_process(
                body_node,
                sensitivity=[signal for _edge, signal in events],
            )
        if all(edge is not None for edge in edge_modes):
            return self._adapt_always_ff(member)
        self._unsupported(
            "同一 always sensitivity 中混合 level 与 edge event 无法安全分类",
            code="HDLX-V2V-MIXED-EVENT",
        )

    def _combinational_process(
        self,
        body_node: JsonObject,
        *,
        sensitivity: list[Identifier],
    ) -> CombinationalProcess:
        return CombinationalProcess(
            label=self._block_label(body_node),
            sensitivity=sensitivity,
            body=self._adapt_statement_body(body_node, process="comb"),
            source_span=self._source_span,
        )

    def _adapt_event_modes(
        self,
        expression: JsonObject,
    ) -> list[tuple[EdgeKind | None, Identifier]]:
        kind = self._kind(expression)
        if kind == "ParenthesizedEventExpression":
            return self._adapt_event_modes(
                self._object(expression.get("expr"), "event expression")
            )
        if kind == "BinaryEventExpression":
            operator = self._kind(
                self._object(expression.get("operatorToken"), "event operator")
            )
            if operator not in {"OrKeyword", "Comma"}:
                self._unsupported(
                    "event control 只支持 or/comma 分隔",
                    code="HDLX-V2V-ALWAYS-EVENT",
                )
            return [
                *self._adapt_event_modes(
                    self._object(expression.get("left"), "left event")
                ),
                *self._adapt_event_modes(
                    self._object(expression.get("right"), "right event")
                ),
            ]
        if kind != "SignalEventExpression":
            self._unsupported(
                "event control 只支持直接 identifier",
                code="HDLX-V2V-ALWAYS-EVENT",
            )

        edge_node = expression.get("edge")
        edge: EdgeKind | None = None
        if edge_node is not None:
            edge_kind = self._kind(self._object(edge_node, "event edge"))
            if edge_kind == "PosEdgeKeyword":
                edge = EdgeKind.POSITIVE
            elif edge_kind == "NegEdgeKeyword":
                edge = EdgeKind.NEGATIVE
            else:
                self._unsupported(
                    f"edge {edge_kind} 不在 v0.3 MVP 内",
                    code="HDLX-V2V-ALWAYS-EVENT",
                )
        signal = self._adapt_expression(
            self._object(expression.get("expr"), "event signal")
        )
        if not isinstance(signal, Identifier):
            self._unsupported(
                "event signal 必须是直接 identifier",
                code="HDLX-V2V-ALWAYS-EVENT",
            )
        return [(edge, signal)]

    def _adapt_data_type(
        self,
        data_type: JsonObject,
    ) -> ScalarType | VectorType | IntegerType:
        if self._kind(data_type) not in {"IntType", "IntegerType"}:
            return super()._adapt_data_type(data_type)
        signing = data_type.get("signing")
        if signing is not None and self._kind(
            self._object(signing, "integer signing")
        ) == "UnsignedKeyword":
            self._unsupported(
                "integer unsigned 不是受支持的 Verilog-2001 integer 语义",
                code="HDLX-V2V-INTEGER-UNSIGNED",
            )
        if data_type.get("dimensions"):
            self._unsupported(
                "integer packed dimension 不在 v0.3 MVP 内",
                code="HDLX-V2V-INTEGER-DIMENSION",
            )
        left = Literal(
            value=31,
            literal_kind=LiteralKind.INTEGER,
            source_span=self._source_span,
        )
        right = Literal(
            value=0,
            literal_kind=LiteralKind.INTEGER,
            source_span=self._source_span,
        )
        return VectorType(
            range=VectorRange(
                left=left,
                right=right,
                direction=RangeDirection.DESCENDING,
                source_span=self._source_span,
            ),
            signed=True,
            four_state=True,
            source_span=self._source_span,
        )

    def _adapt_parameter_declaration(self, declaration: JsonObject, parameters: list[Any]) -> None:
        with self._using_node_span(declaration):
            super()._adapt_parameter_declaration(declaration, parameters)

    def _adapt_signal_declaration(self, declaration: JsonObject) -> list[Any]:
        with self._using_node_span(declaration):
            return super()._adapt_signal_declaration(declaration)

    def _adapt_continuous_assign(self, member: JsonObject) -> list[Any]:
        with self._using_node_span(member):
            return super()._adapt_continuous_assign(member)

    def _adapt_instances(self, member: JsonObject) -> list[Any]:
        with self._using_node_span(member):
            return super()._adapt_instances(member)

    def _adapt_statement(self, statement: JsonObject, *, process: str) -> Any:
        with self._using_node_span(statement):
            return super()._adapt_statement(statement, process=process)

    def _adapt_expression(self, expression: JsonObject) -> Any:
        with self._using_node_span(expression):
            if self._kind(expression) == "BitSelect":
                return self._adapt_expression(
                    self._object(expression.get("expr"), "bit select expression")
                )
            return super()._adapt_expression(expression)

    def _assign_source_spans(
        self,
        canonical_nodes: list[Any],
        syntax_nodes: list[JsonObject],
    ) -> None:
        if len(canonical_nodes) != len(syntax_nodes):
            self._unsupported(
                "Slang declaration 与 Canonical node 数量不一致",
                code="HDLX-V2V-SOURCE-MAP",
            )
        for canonical_node, syntax_node in zip(
            canonical_nodes,
            syntax_nodes,
            strict=True,
        ):
            source_span = self._node_source_span(syntax_node)
            if source_span is not None:
                canonical_node.source_span = source_span

    @contextmanager
    def _using_node_span(self, node: JsonObject) -> Iterator[None]:
        previous = self._source_span
        self._source_span = self._node_source_span(node) or previous
        try:
            yield
        finally:
            self._source_span = previous

    def _node_source_span(self, node: JsonObject) -> SourceSpan | None:
        value = node.get(_SOURCE_SPAN_KEY)
        if value is None:
            return None
        if not isinstance(value, dict):
            self._unsupported(
                "Slang source span 元数据不是对象",
                code="HDLX-V2V-SOURCE-MAP",
            )
        file = value.get("file")
        coordinates = (
            value.get("start_line"),
            value.get("start_column"),
            value.get("end_line"),
            value.get("end_column"),
        )
        if not isinstance(file, str) or not all(type(item) is int for item in coordinates):
            self._unsupported(
                "Slang source span 元数据字段无效",
                code="HDLX-V2V-SOURCE-MAP",
            )
        start_line, start_column, end_line, end_column = coordinates
        return SourceSpan(
            start=SourceLocation(file=file, line=start_line, column=start_column),
            end=SourceLocation(file=file, line=end_line, column=end_column),
        )


__all__ = ["VerilogAdapter"]