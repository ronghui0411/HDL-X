"""基于 pyGHDL/libghdl 的 VHDL frontend backend。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from contextlib import redirect_stdout
from importlib import import_module
from io import StringIO
from pathlib import Path
from threading import RLock
from types import SimpleNamespace
from typing import Any

from hdl_x.diagnostics import FrontendError, HDLXError, UnsupportedConstructError

from .base import GhdlFrontendBackend
from .raw import (
    RawActiveLevel,
    RawArchitecture,
    RawArchitectureItem,
    RawAssociation,
    RawBinaryExpression,
    RawBinaryOperator,
    RawCaseAlternative,
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
    RawResetSpec,
    RawSequentialProcess,
    RawSignal,
    RawSourceLocation,
    RawStatement,
    RawType,
    RawTypeKind,
    RawUnaryExpression,
    RawUnaryOperator,
)
from .runtime import require_pyghdl_runtime

_GENERATE_DOM_TYPE_ERROR = (
    "ModelEntity.__init__() takes from 1 to 2 positional arguments but 4 were given"
)
_LIBGHDL_LOCK = RLock()


def _load_api() -> SimpleNamespace:
    """延迟装入经实际验证的 pyGHDL 6 API。"""

    require_pyghdl_runtime()

    try:
        dom = import_module("pyGHDL.dom")
        expression = import_module("pyGHDL.dom.Expression")
        literal = import_module("pyGHDL.dom.Literal")
        name = import_module("pyGHDL.dom.Name")
        non_standard = import_module("pyGHDL.dom.NonStandard")
        symbol = import_module("pyGHDL.dom.Symbol")
        translate = import_module("pyGHDL.dom._Translate")
        dom_utils = import_module("pyGHDL.dom._Utils")
        libghdl = import_module("pyGHDL.libghdl")
        errorout_memory = import_module("pyGHDL.libghdl.errorout_memory")
        flags = import_module("pyGHDL.libghdl.flags")
        libraries = import_module("pyGHDL.libghdl.libraries")
        name_table = import_module("pyGHDL.libghdl.name_table")
        nodes = import_module("pyGHDL.libghdl.vhdl.nodes")
        vhdl_parse = import_module("pyGHDL.libghdl.vhdl.parse")
        sem = import_module("pyGHDL.libghdl.vhdl.sem")
        node_utils = import_module("pyGHDL.libghdl.utils")
    except (ImportError, OSError) as ex:
        raise FrontendError(
            f"无法装入 pyGHDL/libghdl：{ex}",
            code="HDLX-GHDL-LOAD",
            suggestion="检查 wheel、架构和运行时 DLL 是否与当前 Python 匹配。",
        ) from ex

    return SimpleNamespace(
        Design=non_standard.Design,
        Document=non_standard.Document,
        DOMException=dom.DOMException,
        LibGHDLException=libghdl.LibGHDLException,
        errorout_memory=errorout_memory,
        flags=flags,
        libraries=libraries,
        name_table=name_table,
        Position=dom.Position,
        expression=expression,
        literal=literal,
        name=name,
        symbol=symbol,
        translate=translate,
        dom_utils=dom_utils,
        nodes=nodes,
        vhdl_parse=vhdl_parse,
        sem=sem,
        node_utils=node_utils,
    )


class PyGhdlBackend(GhdlFrontendBackend):
    """运行真实 GHDL 分析并立即隔离为私有 Raw VHDL 表示。"""

    def parse(self, source_path: Path) -> RawDesign:
        path = Path(source_path).resolve()
        if not path.is_file():
            raise FrontendError(
                "VHDL 源文件不存在或不是普通文件。",
                code="HDLX-GHDL-SOURCE",
                file=str(path),
            )

        try:
            source_code = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as ex:
            raise FrontendError(
                f"无法以 UTF-8 读取 VHDL 源文件：{ex}",
                code="HDLX-GHDL-READ",
                file=str(path),
            ) from ex

        api = _load_api()
        with _LIBGHDL_LOCK:
            gather_comments = api.flags.Flag_Gather_Comments.value
            parse_parenthesis = api.vhdl_parse.Flag_Parse_Parenthesis.value
            self._active_source_lines = tuple(source_code.splitlines())
            try:
                # pyGHDL DOM 的 Design.Analyze 只处理 pyVHDLModel 依赖关系，
                # 不能替代 libghdl 的名称、类型和静态性检查。所有输入先在
                # 独立 arena 中完成真实 semantic pass，再构造用于提取的树。
                self._validate_low_level_semantics(api, path, source_code)
                design = api.Design()
                low_level_fallback = False
                try:
                    document = self._create_document(api, path, source_code)
                except TypeError as ex:
                    if str(ex) != _GENERATE_DOM_TYPE_ERROR:
                        raise
                    low_level_fallback = True
                else:
                    if self._contains_generate_statement(api, document):
                        low_level_fallback = True
                    else:
                        library = design.GetLibrary("work")
                        design.AddDocument(document, library)
                        design.LoadDefaultLibraries()
                        design.Analyze()
                if low_level_fallback:
                    # pyGHDL 6 的 generate DOM 翻译与 pyVHDLModel API 不兼容。
                    # 重置后从未被 semantic 改写的语法 IIR 提取，避免损坏的
                    # DOM association；前置独立 pass 已完成真实语义检查。
                    design = api.Design()
                    document = self._create_document(api, path, source_code, dont_translate=True)
                    try:
                        return self._extract_design(api, document, path)
                    finally:
                        # 语法 IIR 属于 libghdl 全局arena，离开fallback即恢复干净状态。
                        api.Design()
                return self._extract_design(api, document, path)
            except HDLXError:
                raise
            except (api.DOMException, api.LibGHDLException, OSError) as ex:
                details = self._format_ghdl_error(ex)
                line, column = self._error_location(details)
                raise FrontendError(
                    f"GHDL 无法分析 VHDL 源文件：{details}",
                    code="HDLX-GHDL-ANALYZE",
                    file=str(path),
                    line=line,
                    column=column,
                    suggestion="修正 GHDL 报告的语法或语义错误后重试。",
                ) from ex
            finally:
                api.flags.Flag_Gather_Comments.value = gather_comments
                api.vhdl_parse.Flag_Parse_Parenthesis.value = parse_parenthesis
                self._active_source_lines = ()

    def _create_document(
        self,
        api: SimpleNamespace,
        path: Path,
        source_code: str,
        *,
        dont_translate: bool = False,
    ) -> Any:
        """构造 pyGHDL Document，并隔离上游 DOM 调试 stdout。"""

        # pyGHDL 6 的部分 unsupported DOM parser 仍含裸 print；这些内容不是
        # HDL-X 诊断，不能污染 CLI stdout。真实错误仍由 CheckForErrors 抛出。
        with redirect_stdout(StringIO()):
            return api.Document(
                path,
                source_code,
                dontTranslate=dont_translate,
            )

    def _validate_low_level_semantics(
        self,
        api: SimpleNamespace,
        path: Path,
        source_code: str,
    ) -> None:
        """对 generate fallback 执行一次独立、完整的 GHDL semantic pass。"""

        design = api.Design()
        design.LoadDefaultLibraries()
        api.errorout_memory.Clear_Errors()
        document = self._create_document(api, path, source_code, dont_translate=True)
        parsed_file = getattr(document, "_Document__ghdlFile", api.nodes.Null_Iir)
        if parsed_file == api.nodes.Null_Iir:
            raise FrontendError(
                "pyGHDL 未公开可供语义分析的 design file。",
                code="HDLX-GHDL-IIR",
                file=str(path),
            )

        api.libraries.Work_Library_Name.value = api.name_table.Get_Identifier("work")
        api.libraries.Load_Work_Library(True)
        unit = api.nodes.Get_First_Design_Unit(parsed_file)
        api.nodes.Set_First_Design_Unit(parsed_file, api.nodes.Null_Iir)
        analyzed_units: list[Any] = []
        analyzed_file = api.nodes.Null_Iir
        try:
            while unit != api.nodes.Null_Iir:
                next_unit = api.nodes.Get_Chain(unit)
                api.nodes.Set_Chain(unit, api.nodes.Null_Iir)
                library_unit = api.nodes.Get_Library_Unit(unit)
                if (
                    library_unit != api.nodes.Null_Iir
                    and api.nodes.Get_Identifier(unit) != api.name_table.Null_Identifier
                ):
                    api.libraries.Add_Design_Unit_Into_Library(unit, False)
                    analyzed_file = api.nodes.Get_Design_File(unit)
                    analyzed_units.append(unit)
                unit = next_unit

            if analyzed_file != api.nodes.Null_Iir:
                source_entry = getattr(
                    document,
                    "_Document__ghdlSourceFileEntry",
                    api.nodes.Null_Iir,
                )
                if source_entry != api.nodes.Null_Iir:
                    api.nodes.Set_Design_File_Source(analyzed_file, source_entry)

            for analyzed_unit in analyzed_units:
                api.sem.Semantic(analyzed_unit)
                api.nodes.Set_Date_State(analyzed_unit, api.nodes.DateStateType.Analyze)
                api.dom_utils.CheckForErrors()
        finally:
            if analyzed_file != api.nodes.Null_Iir:
                api.libraries.Purge_Design_File(analyzed_file)

    @staticmethod
    def _contains_generate_statement(api: SimpleNamespace, document: Any) -> bool:
        """仅在默认DOM能构造时识别仍需低层隔离的generate文件。"""

        design_file = getattr(document, "_Document__ghdlFile", api.nodes.Null_Iir)
        if design_file == api.nodes.Null_Iir:
            return False
        generate_kinds = {
            api.nodes.Iir_Kind.For_Generate_Statement,
            api.nodes.Iir_Kind.If_Generate_Statement,
            api.nodes.Iir_Kind.Case_Generate_Statement,
        }
        first_unit = api.nodes.Get_First_Design_Unit(design_file)
        for design_unit in api.node_utils.chain_iter(first_unit):
            library_unit = api.nodes.Get_Library_Unit(design_unit)
            if (
                library_unit == api.nodes.Null_Iir
                or api.nodes.Get_Kind(library_unit) != api.nodes.Iir_Kind.Architecture_Body
            ):
                continue
            first_statement = api.nodes.Get_Concurrent_Statement_Chain(library_unit)
            if any(
                api.nodes.Get_Kind(statement) in generate_kinds
                for statement in api.node_utils.chain_iter(first_statement)
            ):
                return True
        return False

    def _extract_design(self, api: SimpleNamespace, document: Any, path: Path) -> RawDesign:
        design_file = getattr(document, "_Document__ghdlFile", api.nodes.Null_Iir)
        if design_file == api.nodes.Null_Iir:
            raise FrontendError(
                "pyGHDL 未公开已解析的 design file。",
                code="HDLX-GHDL-IIR",
                file=str(path),
                suggestion="确认当前环境使用经验证的 pyGHDL 6.0.0 backend。",
            )
        entities: list[RawEntity] = []
        architectures: list[RawArchitecture] = []
        first_unit = api.nodes.Get_First_Design_Unit(design_file)
        for design_unit in api.node_utils.chain_iter(first_unit):
            library_unit = api.nodes.Get_Library_Unit(design_unit)
            if library_unit == api.nodes.Null_Iir:
                continue
            kind = api.nodes.Get_Kind(library_unit)
            if kind == api.nodes.Iir_Kind.Entity_Declaration:
                entities.append(self._extract_entity(api, library_unit))
            elif kind == api.nodes.Iir_Kind.Architecture_Body:
                architectures.append(self._extract_architecture(api, library_unit))
            elif kind in {
                api.nodes.Iir_Kind.Package_Declaration,
                api.nodes.Iir_Kind.Package_Body,
                api.nodes.Iir_Kind.Configuration_Declaration,
            }:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    library_unit,
                    f"VHDL design unit {kind_name} 尚未纳入当前 MVP；不能静默忽略。",
                    "HDLX-VHDL-DESIGN-UNIT",
                )
            else:
                # library/use/context clause 也位于 design-file chain，但只提供
                # 分析上下文，不对应可生成的设计单元。
                context_kinds = {
                    getattr(api.nodes.Iir_Kind, name)
                    for name in (
                        "Library_Clause",
                        "Use_Clause",
                        "Context_Reference",
                    )
                    if hasattr(api.nodes.Iir_Kind, name)
                }
                if kind not in context_kinds:
                    kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                    self._raise_unsupported(
                        api,
                        library_unit,
                        f"VHDL design unit {kind_name} 尚未纳入当前 MVP；不能静默忽略。",
                        "HDLX-VHDL-DESIGN-UNIT",
                    )

        if not entities:
            raise UnsupportedConstructError(
                "输入文件不包含可转换的 VHDL entity。",
                code="HDLX-VHDL-NO-ENTITY",
                file=str(path),
            )

        return RawDesign(
            source_path=path,
            entities=tuple(entities),
            architectures=tuple(architectures),
        )

    def _extract_entity(self, api: SimpleNamespace, entity: Any) -> RawEntity:
        declaration = api.nodes.Get_Declaration_Chain(entity)
        if declaration != api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                declaration,
                "entity declarative item 尚未纳入当前 VHDL 子集。",
                "HDLX-VHDL-ENTITY-DECLARATION",
            )

        parameters = tuple(
            self._extract_parameter(api, node)
            for node in api.node_utils.chain_iter(api.nodes.Get_Generic_Chain(entity))
        )
        ports = tuple(
            self._extract_port(api, node)
            for node in api.node_utils.chain_iter(api.nodes.Get_Port_Chain(entity))
        )
        return RawEntity(
            name=api.dom_utils.GetNameOfNode(entity),
            parameters=parameters,
            ports=ports,
            source=self._source_from_iir(api, entity),
        )

    def _extract_parameter(self, api: SimpleNamespace, node: Any) -> RawParameter:
        name = api.dom_utils.GetNameOfNode(node)
        subtype = api.translate.GetSubtypeIndicationFromNode(node, "generic", name)
        default_node = api.nodes.Get_Default_Value(node)
        default = (
            None
            if default_node == api.nodes.Null_Iir
            else self._expression_from_iir(api, default_node)
        )
        return RawParameter(
            name=name,
            type=self._convert_type(api, subtype),
            default=default,
            source=self._source_from_iir(api, node),
        )

    def _extract_port(
        self,
        api: SimpleNamespace,
        node: Any,
        *,
        allow_default: bool = False,
    ) -> RawPort:
        name = api.dom_utils.GetNameOfNode(node)
        mode = api.nodes.Get_Mode(node)
        mode_map = {
            api.nodes.Iir_Mode.In_Mode: RawPortDirection.IN,
            api.nodes.Iir_Mode.Out_Mode: RawPortDirection.OUT,
            api.nodes.Iir_Mode.Inout_Mode: RawPortDirection.INOUT,
        }
        try:
            direction = mode_map[mode]
        except KeyError:
            mode_name = self._enum_name(api.nodes.Iir_Mode, mode)
            self._raise_unsupported(
                api,
                node,
                f"端口 {name!r} 使用未支持的 VHDL mode {mode_name}。",
                "HDLX-VHDL-PORT-MODE",
            )

        default_node = api.nodes.Get_Default_Value(node)
        if default_node != api.nodes.Null_Iir and not allow_default:
            self._raise_unsupported(
                api,
                node,
                f"端口 {name!r} 的默认表达式尚未纳入当前子集。",
                "HDLX-VHDL-PORT-DEFAULT",
            )

        subtype = api.translate.GetSubtypeIndicationFromNode(node, "port", name)
        return RawPort(
            name=name,
            direction=direction,
            type=self._convert_type(api, subtype),
            source=self._source_from_iir(api, node),
            default=(
                None
                if default_node == api.nodes.Null_Iir
                else self._expression_from_iir(api, default_node)
            ),
        )

    def _extract_architecture(self, api: SimpleNamespace, architecture: Any) -> RawArchitecture:
        signals, components = self._extract_declarations(api, architecture)
        components_by_name = {component.name.casefold(): component for component in components}
        items = self._extract_concurrent_items(
            api,
            api.nodes.Get_Concurrent_Statement_Chain(architecture),
            components_by_name,
        )

        entity_name_node = api.nodes.Get_Entity_Name(architecture)
        if entity_name_node == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                architecture,
                "architecture 缺少所属 entity 名称。",
                "HDLX-VHDL-ARCHITECTURE-ENTITY",
            )
        return RawArchitecture(
            name=api.dom_utils.GetNameOfNode(architecture),
            entity_name=api.dom_utils.GetNameOfNode(entity_name_node),
            items=items,
            source=self._source_from_iir(api, architecture),
            signals=signals,
            components=components,
        )

    def _extract_concurrent_items(
        self,
        api: SimpleNamespace,
        chain: Any,
        components_by_name: Mapping[str, RawComponentDeclaration],
    ) -> tuple[RawArchitectureItem, ...]:
        items: list[RawArchitectureItem] = []
        for statement in api.node_utils.chain_iter(chain):
            kind = api.nodes.Get_Kind(statement)
            if kind == api.nodes.Iir_Kind.Concurrent_Simple_Signal_Assignment:
                items.append(self._extract_concurrent_assignment(api, statement))
            elif kind == api.nodes.Iir_Kind.Concurrent_Conditional_Signal_Assignment:
                items.append(self._extract_conditional_concurrent_assignment(api, statement))
            elif kind in {
                api.nodes.Iir_Kind.Sensitized_Process_Statement,
                api.nodes.Iir_Kind.Process_Statement,
            }:
                items.append(
                    self._extract_process(
                        api,
                        statement,
                        has_sensitivity=(kind == api.nodes.Iir_Kind.Sensitized_Process_Statement),
                    )
                )
            elif kind == api.nodes.Iir_Kind.Component_Instantiation_Statement:
                items.append(self._extract_instance(api, statement, components_by_name))
            elif kind == api.nodes.Iir_Kind.For_Generate_Statement:
                items.append(self._extract_for_generate(api, statement, components_by_name))
            elif kind == api.nodes.Iir_Kind.If_Generate_Statement:
                items.append(self._extract_if_generate(api, statement, components_by_name))
            elif kind == api.nodes.Iir_Kind.Case_Generate_Statement:
                self._raise_unsupported(
                    api,
                    statement,
                    "case-generate 尚未纳入当前 VHDL 子集。",
                    "HDLX-VHDL-GENERATE-CONSTRUCT",
                )
            else:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    statement,
                    f"并发构造 {kind_name} 尚未纳入当前 VHDL 子集。",
                    "HDLX-VHDL-CONCURRENT-CONSTRUCT",
                )
        return tuple(items)

    def _extract_for_generate(
        self,
        api: SimpleNamespace,
        statement: Any,
        components_by_name: Mapping[str, RawComponentDeclaration],
    ) -> RawForGenerate:
        label = self._require_generate_label(api, statement)
        parameter = api.nodes.Get_Parameter_Specification(statement)
        if (
            parameter == api.nodes.Null_Iir
            or api.nodes.Get_Kind(parameter) != api.nodes.Iir_Kind.Iterator_Declaration
        ):
            self._raise_unsupported(
                api,
                statement,
                "for-generate 缺少可识别的迭代参数。",
                "HDLX-VHDL-GENERATE-ITERATOR",
            )
        discrete_range = api.nodes.Get_Discrete_Range(parameter)
        if (
            discrete_range == api.nodes.Null_Iir
            or api.nodes.Get_Kind(discrete_range) != api.nodes.Iir_Kind.Range_Expression
        ):
            self._raise_unsupported(
                api,
                parameter,
                "for-generate 仅支持显式离散范围。",
                "HDLX-VHDL-GENERATE-RANGE",
            )
        left = api.nodes.Get_Left_Limit_Expr(discrete_range)
        right = api.nodes.Get_Right_Limit_Expr(discrete_range)
        if left == api.nodes.Null_Iir or right == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                discrete_range,
                "for-generate 范围缺少左右边界表达式。",
                "HDLX-VHDL-GENERATE-RANGE",
            )
        direction = {
            0: RawRangeDirection.TO,
            1: RawRangeDirection.DOWNTO,
        }.get(int(api.nodes.Get_Direction(discrete_range)))
        if direction is None:
            self._raise_unsupported(
                api,
                discrete_range,
                "for-generate 使用未知范围方向。",
                "HDLX-VHDL-GENERATE-RANGE",
            )
        body = api.nodes.Get_Generate_Statement_Body(statement)
        return RawForGenerate(
            label=label,
            index_name=api.dom_utils.GetNameOfNode(parameter),
            range=RawRange(
                left=self._expression_from_iir(api, left),
                right=self._expression_from_iir(api, right),
                direction=direction,
                source=self._source_from_iir(api, discrete_range),
            ),
            body=self._extract_generate_body(api, body, statement, components_by_name),
            source=self._source_from_iir(api, statement),
        )

    def _extract_if_generate(
        self,
        api: SimpleNamespace,
        statement: Any,
        components_by_name: Mapping[str, RawComponentDeclaration],
    ) -> RawIfGenerate:
        label = self._require_generate_label(api, statement)
        condition = api.nodes.Get_Condition(statement)
        if condition == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                statement,
                "if-generate 缺少条件表达式。",
                "HDLX-VHDL-GENERATE-CONDITION",
            )
        then_body = self._extract_generate_body(
            api,
            api.nodes.Get_Generate_Statement_Body(statement),
            statement,
            components_by_name,
        )
        else_body: tuple[RawArchitectureItem, ...] = ()
        else_clause = api.nodes.Get_Generate_Else_Clause(statement)
        if else_clause != api.nodes.Null_Iir:
            if api.nodes.Get_Condition(else_clause) != api.nodes.Null_Iir:
                self._raise_unsupported(
                    api,
                    else_clause,
                    "elsif-generate 尚未纳入当前 VHDL 子集。",
                    "HDLX-VHDL-GENERATE-ELSIF",
                )
            else_body = self._extract_generate_body(
                api,
                api.nodes.Get_Generate_Statement_Body(else_clause),
                statement,
                components_by_name,
            )
            if api.nodes.Get_Generate_Else_Clause(else_clause) != api.nodes.Null_Iir:
                self._raise_unsupported(
                    api,
                    else_clause,
                    "generate else 分支链结构无法安全转换。",
                    "HDLX-VHDL-GENERATE-ELSE",
                )
        return RawIfGenerate(
            label=label,
            condition=self._expression_from_iir(api, condition),
            then_body=then_body,
            else_body=else_body,
            source=self._source_from_iir(api, statement),
        )

    def _extract_generate_body(
        self,
        api: SimpleNamespace,
        body: Any,
        owner: Any,
        inherited_components: Mapping[str, RawComponentDeclaration],
    ) -> tuple[RawArchitectureItem, ...]:
        if body == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                owner,
                "generate statement 缺少可识别的 statement body。",
                "HDLX-VHDL-GENERATE-BODY",
            )
        signals, components = self._extract_declarations(api, body)
        components_by_name = dict(inherited_components)
        components_by_name.update(
            (component.name.casefold(), component) for component in components
        )
        concurrent = self._extract_concurrent_items(
            api,
            api.nodes.Get_Concurrent_Statement_Chain(body),
            components_by_name,
        )
        return (*signals, *concurrent)

    def _require_generate_label(self, api: SimpleNamespace, statement: Any) -> str:
        label = self._label_from_iir(api, statement)
        if label is None:
            self._raise_unsupported(
                api,
                statement,
                "generate statement 缺少 label，不能保持源层次。",
                "HDLX-VHDL-GENERATE-LABEL",
            )
        return label

    def _extract_declarations(
        self, api: SimpleNamespace, owner: Any
    ) -> tuple[tuple[RawSignal, ...], tuple[RawComponentDeclaration, ...]]:
        signals: list[RawSignal] = []
        components: list[RawComponentDeclaration] = []
        declaration = api.nodes.Get_Declaration_Chain(owner)
        while declaration != api.nodes.Null_Iir:
            kind = api.nodes.Get_Kind(declaration)
            if kind == api.nodes.Iir_Kind.Component_Declaration:
                components.append(self._extract_component_declaration(api, declaration))
                declaration = api.nodes.Get_Chain(declaration)
                continue
            if kind != api.nodes.Iir_Kind.Signal_Declaration:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    declaration,
                    f"并发作用域声明 {kind_name} 尚未纳入当前 VHDL 子集。",
                    "HDLX-VHDL-ARCHITECTURE-DECLARATION",
                )

            first = declaration
            names = [(api.dom_utils.GetNameOfNode(first), first)]
            declaration = api.nodes.Get_Chain(first)
            if api.nodes.Get_Has_Identifier_List(first):
                while declaration != api.nodes.Null_Iir:
                    if api.nodes.Get_Kind(declaration) != api.nodes.Iir_Kind.Signal_Declaration:
                        self._raise_unsupported(
                            api,
                            declaration,
                            "signal 标识符列表包含非 signal 节点。",
                            "HDLX-VHDL-SIGNAL-IDENTIFIER-LIST",
                        )
                    if api.nodes.Get_Subtype_Indication(declaration) != api.nodes.Null_Iir:
                        break
                    names.append((api.dom_utils.GetNameOfNode(declaration), declaration))
                    has_more = api.nodes.Get_Has_Identifier_List(declaration)
                    declaration = api.nodes.Get_Chain(declaration)
                    if not has_more:
                        break

            if api.nodes.Get_Default_Value(first) != api.nodes.Null_Iir:
                self._raise_unsupported(
                    api,
                    first,
                    "并发作用域 signal 初始值尚未纳入当前 RTL 子集。",
                    "HDLX-VHDL-SIGNAL-INITIALIZER",
                )
            first_name = names[0][0]
            subtype = api.translate.GetSubtypeIndicationFromNode(first, "signal", first_name)
            raw_type = self._convert_type(api, subtype)
            signals.extend(
                RawSignal(
                    name=name,
                    type=raw_type,
                    source=self._source_from_iir(api, node),
                )
                for name, node in names
            )
        return tuple(signals), tuple(components)

    def _extract_component_declaration(
        self, api: SimpleNamespace, declaration: Any
    ) -> RawComponentDeclaration:
        """从 pyGHDL 6 IIR 的 component declaration 保存完整接口。"""

        parameters = tuple(
            self._extract_parameter(api, node)
            for node in api.node_utils.chain_iter(api.nodes.Get_Generic_Chain(declaration))
        )
        ports = tuple(
            self._extract_port(api, node, allow_default=True)
            for node in api.node_utils.chain_iter(api.nodes.Get_Port_Chain(declaration))
        )
        return RawComponentDeclaration(
            name=api.dom_utils.GetNameOfNode(declaration),
            parameters=parameters,
            ports=ports,
            source=self._source_from_iir(api, declaration),
        )

    def _extract_instance(
        self,
        api: SimpleNamespace,
        statement: Any,
        components_by_name: Mapping[str, RawComponentDeclaration],
    ) -> RawInstance:
        label = self._label_from_iir(api, statement)
        if label is None:
            self._raise_unsupported(
                api,
                statement,
                "实例缺少 VHDL label，不能保持层次名称。",
                "HDLX-VHDL-INSTANCE-LABEL",
            )

        instantiated_unit = api.nodes.Get_Instantiated_Unit(statement)
        unit_kind = api.nodes.Get_Kind(instantiated_unit)
        component_declaration = None
        if unit_kind == api.nodes.Iir_Kind.Entity_Aspect_Entity:
            entity_name = api.nodes.Get_Entity_Name(instantiated_unit)
            if entity_name == api.nodes.Null_Iir:
                self._raise_unsupported(
                    api,
                    instantiated_unit,
                    "direct entity instance 缺少 entity 名称。",
                    "HDLX-VHDL-INSTANCE-UNIT",
                )
            referenced_unit = api.dom_utils.GetNameOfNode(entity_name)
            instantiation_kind = RawInstantiationKind.DIRECT_ENTITY
        elif unit_kind in {
            api.nodes.Iir_Kind.Simple_Name,
            api.nodes.Iir_Kind.Selected_Name,
        }:
            referenced_unit = api.dom_utils.GetNameOfNode(instantiated_unit)
            instantiation_kind = RawInstantiationKind.COMPONENT
            component_declaration = components_by_name.get(referenced_unit.casefold())
            if component_declaration is None:
                self._raise_unsupported(
                    api,
                    instantiated_unit,
                    f"component instance 引用的声明 {referenced_unit!r} 不在当前词法作用域中。",
                    "HDLX-VHDL-COMPONENT-DECLARATION",
                )
        else:
            kind_name = self._enum_name(api.nodes.Iir_Kind, unit_kind)
            self._raise_unsupported(
                api,
                instantiated_unit,
                f"实例单元类别 {kind_name} 尚未纳入当前 VHDL 子集。",
                "HDLX-VHDL-INSTANCE-UNIT",
            )

        parameters = self._extract_associations(
            api,
            api.nodes.Get_Generic_Map_Aspect_Chain(statement),
            role="generic",
            allow_open=False,
        )
        ports = self._extract_associations(
            api,
            api.nodes.Get_Port_Map_Aspect_Chain(statement),
            role="port",
            allow_open=True,
        )
        return RawInstance(
            referenced_unit=referenced_unit,
            name=label,
            parameter_associations=parameters,
            port_associations=ports,
            source=self._source_from_iir(api, statement),
            instantiation_kind=instantiation_kind,
            component_declaration=component_declaration,
        )

    def _extract_associations(
        self,
        api: SimpleNamespace,
        chain: Any,
        *,
        role: str,
        allow_open: bool,
    ) -> tuple[RawAssociation, ...]:
        associations: list[RawAssociation] = []
        for index, association in enumerate(api.node_utils.chain_iter(chain)):
            kind = api.nodes.Get_Kind(association)
            if kind not in {
                api.nodes.Iir_Kind.Association_Element_By_Expression,
                api.nodes.Iir_Kind.Association_Element_Open,
            }:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    association,
                    f"{role} map association 类别 {kind_name} 不能安全转换。",
                    "HDLX-VHDL-ASSOCIATION",
                )

            formal_node = api.nodes.Get_Formal(association)
            formal = None
            if formal_node != api.nodes.Null_Iir:
                formal_kind = api.nodes.Get_Kind(formal_node)
                if formal_kind != api.nodes.Iir_Kind.Simple_Name:
                    kind_name = self._enum_name(api.nodes.Iir_Kind, formal_kind)
                    self._raise_unsupported(
                        api,
                        formal_node,
                        f"{role} map formal 类别 {kind_name} 尚未纳入当前子集。",
                        "HDLX-VHDL-ASSOCIATION-FORMAL",
                    )
                formal = api.dom_utils.GetNameOfNode(formal_node)

            if kind == api.nodes.Iir_Kind.Association_Element_Open:
                if not allow_open:
                    self._raise_unsupported(
                        api,
                        association,
                        "generic map 的 open association 不能安全转换为 Verilog parameter。",
                        "HDLX-VHDL-GENERIC-OPEN",
                    )
                value = None
            else:
                actual = api.nodes.Get_Actual(association)
                if actual == api.nodes.Null_Iir:
                    self._raise_unsupported(
                        api,
                        association,
                        f"{role} map association 缺少 actual。",
                        "HDLX-VHDL-ASSOCIATION-ACTUAL",
                    )
                value = self._expression_from_iir(api, actual)

            associations.append(
                RawAssociation(
                    formal=formal,
                    position=index if formal is None else None,
                    value=value,
                    source=self._source_from_iir(api, association),
                )
            )
        return tuple(associations)

    def _extract_concurrent_assignment(
        self, api: SimpleNamespace, statement: Any
    ) -> RawConcurrentAssignment:
        value = self._extract_single_waveform_value(
            api, api.nodes.Get_Waveform_Chain(statement), statement
        )
        target_node = api.nodes.Get_Target(statement)
        return RawConcurrentAssignment(
            target=self._expression_from_iir(api, target_node),
            value=value,
            source=self._source_from_iir(api, statement),
        )

    def _extract_conditional_concurrent_assignment(
        self, api: SimpleNamespace, statement: Any
    ) -> RawConcurrentAssignment:
        clauses: list[tuple[Any, RawExpression, RawSourceLocation | None]] = []
        conditional = api.nodes.Get_Conditional_Waveform_Chain(statement)
        for clause in api.node_utils.chain_iter(conditional):
            condition_node = api.nodes.Get_Condition(clause)
            value = self._extract_single_waveform_value(
                api, api.nodes.Get_Waveform_Chain(clause), clause
            )
            clauses.append((condition_node, value, self._source_from_iir(api, clause)))

        if not clauses or clauses[-1][0] != api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                statement,
                "缺少最终 else 的条件并发赋值可能保留旧值，不能降为连续表达式。",
                "HDLX-VHDL-CONDITIONAL-INCOMPLETE",
            )
        if any(condition == api.nodes.Null_Iir for condition, _, _ in clauses[:-1]):
            self._raise_unsupported(
                api,
                statement,
                "条件并发赋值的无条件分支必须位于最后。",
                "HDLX-VHDL-CONDITIONAL-ORDER",
            )

        value = clauses[-1][1]
        for condition_node, when_true, source in reversed(clauses[:-1]):
            value = RawConditionalExpression(
                condition=self._expression_from_iir(api, condition_node),
                when_true=when_true,
                when_false=value,
                source=source,
            )
        return RawConcurrentAssignment(
            target=self._expression_from_iir(api, api.nodes.Get_Target(statement)),
            value=value,
            source=self._source_from_iir(api, statement),
        )

    def _extract_single_waveform_value(
        self, api: SimpleNamespace, waveform: Any, owner: Any
    ) -> RawExpression:
        if waveform == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                owner,
                "并发信号赋值缺少可转换波形。",
                "HDLX-VHDL-WAVEFORM",
            )
        if api.nodes.Get_Chain(waveform) != api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                owner,
                "多元素 waveform 尚未纳入当前 VHDL 子集。",
                "HDLX-VHDL-WAVEFORM",
            )
        if api.nodes.Get_Time(waveform) != api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                waveform,
                "带延时的信号赋值不可安全转换为当前 RTL 子集。",
                "HDLX-VHDL-DELAY",
            )
        value_node = api.nodes.Get_We_Value(waveform)
        if value_node == api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                waveform,
                "unaffected 或空 waveform 尚未纳入当前 RTL 子集。",
                "HDLX-VHDL-WAVEFORM",
            )
        return self._expression_from_iir(api, value_node)

    def _extract_process(
        self, api: SimpleNamespace, process: Any, *, has_sensitivity: bool
    ) -> RawCombinationalProcess | RawSequentialProcess:
        self._reject_process_declarations(api, process)
        if not has_sensitivity:
            return self._extract_combinational_process(api, process, has_sensitivity=False)

        sensitivity = self._extract_process_sensitivity(api, process)
        sequential = self._try_extract_sequential_process(api, process, sensitivity)
        if sequential is not None:
            return sequential
        return self._extract_combinational_process(
            api, process, has_sensitivity=True, sensitivity=sensitivity
        )

    def _reject_process_declarations(self, api: SimpleNamespace, process: Any) -> None:
        """在过程分类前统一拒绝尚未建模的本地声明。"""

        declaration = api.nodes.Get_Declaration_Chain(process)
        if declaration != api.nodes.Null_Iir:
            self._raise_unsupported(
                api,
                declaration,
                "process 本地声明尚未纳入当前 VHDL 子集。",
                "HDLX-VHDL-PROCESS-DECLARATION",
            )

    def _extract_process_sensitivity(
        self, api: SimpleNamespace, process: Any
    ) -> tuple[RawIdentifier, ...]:
        sensitivity_list = api.nodes.Get_Sensitivity_List(process)
        if sensitivity_list == api.nodes.Iir_List_All:
            return ()
        if sensitivity_list == api.nodes.Null_Iir_List:
            self._raise_unsupported(
                api,
                process,
                "process 的敏感列表为空。",
                "HDLX-VHDL-PROCESS-SENSITIVITY",
            )

        sensitivity: list[RawIdentifier] = []
        for item in api.node_utils.list_iter(sensitivity_list):
            expression = self._expression_from_iir(api, item)
            if not isinstance(expression, RawIdentifier):
                self._raise_unsupported(
                    api,
                    item,
                    "process 敏感列表只支持简单信号名称。",
                    "HDLX-VHDL-PROCESS-SENSITIVITY",
                )
            sensitivity.append(expression)
        return tuple(sensitivity)

    def _try_extract_sequential_process(
        self,
        api: SimpleNamespace,
        process: Any,
        sensitivity: tuple[RawIdentifier, ...],
    ) -> RawSequentialProcess | None:
        chain = api.nodes.Get_Sequential_Statement_Chain(process)
        if chain == api.nodes.Null_Iir:
            return None

        statements = tuple(api.node_utils.chain_iter(chain))
        if len(statements) != 1:
            if any(self._contains_edge_call(api, node) for node in statements):
                self._raise_unsupported(
                    api,
                    process,
                    "时序 process 必须只有一个顶层 if 语句。",
                    "HDLX-VHDL-SEQUENTIAL-SHAPE",
                )
            return None

        top = statements[0]
        if api.nodes.Get_Kind(top) != api.nodes.Iir_Kind.If_Statement:
            return None

        top_condition = api.nodes.Get_Condition(top)
        top_edge = self._match_edge_call(api, top_condition)
        if top_edge is not None:
            if api.nodes.Get_Else_Clause(top) != api.nodes.Null_Iir:
                self._raise_unsupported(
                    api,
                    top,
                    "时钟边沿顶层 if 不能具有 elsif 或 else 分支。",
                    "HDLX-VHDL-SEQUENTIAL-SHAPE",
                )
            clock, edge = top_edge
            self._validate_clock_sensitivity(api, process, sensitivity, clock, None)
            clock_body = tuple(
                api.node_utils.chain_iter(api.nodes.Get_Sequential_Statement_Chain(top))
            )
            reset = None
            reset_body: tuple[RawStatement, ...] = ()
            body_nodes = clock_body
            if len(clock_body) == 1 and (
                api.nodes.Get_Kind(clock_body[0]) == api.nodes.Iir_Kind.If_Statement
            ):
                inner = clock_body[0]
                reset_match = self._match_reset_condition(api, api.nodes.Get_Condition(inner))
                if reset_match is not None:
                    reset_signal, active_level = reset_match
                    else_clauses = self._collect_else_clauses(api, inner)
                    if (
                        len(else_clauses) == 1
                        and else_clauses[0][0] == api.nodes.Null_Iir
                        and self._is_constant_assignment_chain(
                            api, api.nodes.Get_Sequential_Statement_Chain(inner)
                        )
                    ):
                        reset = RawResetSpec(
                            signal=reset_signal,
                            kind=RawResetKind.SYNCHRONOUS,
                            active_level=active_level,
                            source=self._source_from_iir(api, inner),
                        )
                        reset_body = self._extract_sequential_chain(
                            api, api.nodes.Get_Sequential_Statement_Chain(inner)
                        )
                        body_nodes = tuple(
                            api.node_utils.chain_iter(
                                api.nodes.Get_Sequential_Statement_Chain(else_clauses[0][1])
                            )
                        )
            return RawSequentialProcess(
                label=self._label_from_iir(api, process),
                sensitivity=sensitivity,
                clock=clock,
                edge=edge,
                reset=reset,
                reset_body=reset_body,
                body=self._extract_sequential_nodes(api, body_nodes),
                source=self._source_from_iir(api, process),
            )

        reset_match = self._match_reset_condition(api, top_condition)
        else_clauses = self._collect_else_clauses(api, top)
        edge_clauses = [
            (condition, clause, self._match_edge_call(api, condition))
            for condition, clause in else_clauses
            if condition != api.nodes.Null_Iir
        ]
        matched_edges = [item for item in edge_clauses if item[2] is not None]
        if not matched_edges:
            if self._statement_contains_nested_edge(api, top):
                self._raise_unsupported(
                    api,
                    top,
                    "嵌套或条件化的时钟边沿无法安全分类。",
                    "HDLX-VHDL-SEQUENTIAL-AMBIGUOUS",
                )
            return None
        if reset_match is None or len(matched_edges) != 1 or len(else_clauses) != 1:
            self._raise_unsupported(
                api,
                top,
                "异步时序 process 必须是 reset 条件后接单一 edge elsif。",
                "HDLX-VHDL-SEQUENTIAL-AMBIGUOUS",
            )

        reset_signal, active_level = reset_match
        _, edge_clause, edge_match = matched_edges[0]
        assert edge_match is not None
        clock, edge = edge_match
        self._validate_clock_sensitivity(api, process, sensitivity, clock, reset_signal)
        return RawSequentialProcess(
            label=self._label_from_iir(api, process),
            sensitivity=sensitivity,
            clock=clock,
            edge=edge,
            reset=RawResetSpec(
                signal=reset_signal,
                kind=RawResetKind.ASYNCHRONOUS,
                active_level=active_level,
                source=self._source_from_iir(api, top),
            ),
            reset_body=self._extract_sequential_chain(
                api, api.nodes.Get_Sequential_Statement_Chain(top)
            ),
            body=self._extract_sequential_chain(
                api, api.nodes.Get_Sequential_Statement_Chain(edge_clause)
            ),
            source=self._source_from_iir(api, process),
        )

    def _match_edge_call(
        self, api: SimpleNamespace, condition: Any
    ) -> tuple[RawIdentifier, RawEdgeKind] | None:
        if condition == api.nodes.Null_Iir:
            return None
        if api.nodes.Get_Kind(condition) != api.nodes.Iir_Kind.Parenthesis_Name:
            return None

        prefix = api.nodes.Get_Prefix(condition)
        if (
            prefix == api.nodes.Null_Iir
            or api.nodes.Get_Kind(prefix) != api.nodes.Iir_Kind.Simple_Name
        ):
            return None
        function_name = str(api.dom_utils.GetNameOfNode(prefix)).casefold()
        edge_map = {
            "rising_edge": RawEdgeKind.POSITIVE,
            "falling_edge": RawEdgeKind.NEGATIVE,
        }
        edge = edge_map.get(function_name)
        if edge is None:
            return None

        associations = tuple(api.node_utils.chain_iter(api.nodes.Get_Association_Chain(condition)))
        if len(associations) != 1:
            self._raise_unsupported(
                api,
                condition,
                f"{function_name} 必须具有一个位置参数。",
                "HDLX-VHDL-EDGE-SHAPE",
            )
        association = associations[0]
        if (
            api.nodes.Get_Kind(association) != api.nodes.Iir_Kind.Association_Element_By_Expression
            or api.nodes.Get_Formal(association) != api.nodes.Null_Iir
        ):
            self._raise_unsupported(
                api,
                condition,
                f"{function_name} 只支持一个位置时钟参数。",
                "HDLX-VHDL-EDGE-SHAPE",
            )
        actual = api.nodes.Get_Actual(association)
        if (
            actual == api.nodes.Null_Iir
            or api.nodes.Get_Kind(actual) != api.nodes.Iir_Kind.Simple_Name
        ):
            self._raise_unsupported(
                api,
                condition,
                f"{function_name} 的时钟参数必须是简单信号名称。",
                "HDLX-VHDL-EDGE-SHAPE",
            )
        return (
            RawIdentifier(
                name=str(api.dom_utils.GetNameOfNode(actual)),
                source=self._source_from_iir(api, actual),
            ),
            edge,
        )

    def _match_reset_condition(
        self, api: SimpleNamespace, condition: Any
    ) -> tuple[RawIdentifier, RawActiveLevel] | None:
        if (
            condition == api.nodes.Null_Iir
            or api.nodes.Get_Kind(condition) != api.nodes.Iir_Kind.Equality_Operator
        ):
            return None
        left = api.nodes.Get_Left(condition)
        right = api.nodes.Get_Right(condition)
        for signal_node, literal_node in ((left, right), (right, left)):
            if (
                api.nodes.Get_Kind(signal_node) == api.nodes.Iir_Kind.Simple_Name
                and api.nodes.Get_Kind(literal_node) == api.nodes.Iir_Kind.Character_Literal
            ):
                value = api.name_table.Get_Character(api.nodes.Get_Identifier(literal_node))
                active_map = {"1": RawActiveLevel.HIGH, "0": RawActiveLevel.LOW}
                active_level = active_map.get(str(value))
                if active_level is None:
                    return None
                return (
                    RawIdentifier(
                        name=str(api.dom_utils.GetNameOfNode(signal_node)),
                        source=self._source_from_iir(api, signal_node),
                    ),
                    active_level,
                )
        return None

    def _collect_else_clauses(self, api: SimpleNamespace, statement: Any) -> list[tuple[Any, Any]]:
        clauses: list[tuple[Any, Any]] = []
        clause = api.nodes.Get_Else_Clause(statement)
        while clause != api.nodes.Null_Iir:
            clauses.append((api.nodes.Get_Condition(clause), clause))
            clause = api.nodes.Get_Else_Clause(clause)
        return clauses

    def _contains_edge_call(self, api: SimpleNamespace, statement: Any) -> bool:
        if api.nodes.Get_Kind(statement) != api.nodes.Iir_Kind.If_Statement:
            return False
        if self._match_edge_call(api, api.nodes.Get_Condition(statement)) is not None:
            return True
        return any(
            condition != api.nodes.Null_Iir and self._match_edge_call(api, condition) is not None
            for condition, _ in self._collect_else_clauses(api, statement)
        )

    def _statement_contains_nested_edge(self, api: SimpleNamespace, statement: Any) -> bool:
        if api.nodes.Get_Kind(statement) != api.nodes.Iir_Kind.If_Statement:
            return False
        if self._contains_edge_call(api, statement):
            return True
        branches = [
            api.nodes.Get_Sequential_Statement_Chain(statement),
            *(
                api.nodes.Get_Sequential_Statement_Chain(clause)
                for _, clause in self._collect_else_clauses(api, statement)
            ),
        ]
        return any(
            self._statement_contains_nested_edge(api, child)
            for chain in branches
            for child in api.node_utils.chain_iter(chain)
        )

    def _is_constant_assignment_chain(self, api: SimpleNamespace, chain: Any) -> bool:
        statements = tuple(api.node_utils.chain_iter(chain))
        if not statements:
            return False
        for statement in statements:
            if (
                api.nodes.Get_Kind(statement)
                != api.nodes.Iir_Kind.Simple_Signal_Assignment_Statement
            ):
                return False
            waveform = api.nodes.Get_Waveform_Chain(statement)
            if (
                waveform == api.nodes.Null_Iir
                or api.nodes.Get_Chain(waveform) != api.nodes.Null_Iir
            ):
                return False
            if api.nodes.Get_Time(waveform) != api.nodes.Null_Iir:
                return False
            value = self._expression_from_iir(api, api.nodes.Get_We_Value(waveform))
            if not isinstance(value, RawLiteral):
                return False
        return True

    def _validate_clock_sensitivity(
        self,
        api: SimpleNamespace,
        process: Any,
        sensitivity: tuple[RawIdentifier, ...],
        clock: RawIdentifier,
        reset: RawIdentifier | None,
    ) -> None:
        names = [item.name.casefold() for item in sensitivity]
        expected = {clock.name.casefold()}
        if reset is not None:
            expected.add(reset.name.casefold())
        if len(names) != len(set(names)) or set(names) != expected:
            self._raise_unsupported(
                api,
                process,
                "时序 process 敏感列表必须精确包含时钟及可选异步复位信号。",
                "HDLX-VHDL-SEQUENTIAL-SENSITIVITY",
            )

    def _extract_sequential_nodes(
        self, api: SimpleNamespace, nodes: tuple[Any, ...]
    ) -> tuple[RawStatement, ...]:
        if not nodes:
            return ()
        return self._extract_sequential_chain(api, nodes[0])

    def _extract_combinational_process(
        self,
        api: SimpleNamespace,
        process: Any,
        *,
        has_sensitivity: bool,
        sensitivity: tuple[RawIdentifier, ...] | None = None,
    ) -> RawCombinationalProcess:
        body = self._extract_sequential_chain(
            api, api.nodes.Get_Sequential_Statement_Chain(process)
        )
        if not has_sensitivity:
            self._raise_unsupported(
                api,
                process,
                "无敏感列表的 process 不能安全判定为组合逻辑。",
                "HDLX-VHDL-PROCESS-SENSITIVITY",
            )

        if sensitivity is None:
            sensitivity = self._extract_process_sensitivity(api, process)

        return RawCombinationalProcess(
            label=self._label_from_iir(api, process),
            sensitivity=sensitivity,
            body=body,
            source=self._source_from_iir(api, process),
        )

    def _extract_sequential_chain(
        self, api: SimpleNamespace, chain: Any
    ) -> tuple[RawStatement, ...]:
        statements: list[RawStatement] = []
        for statement in api.node_utils.chain_iter(chain):
            kind = api.nodes.Get_Kind(statement)
            if kind == api.nodes.Iir_Kind.Simple_Signal_Assignment_Statement:
                statements.append(self._extract_procedural_assignment(api, statement))
            elif kind == api.nodes.Iir_Kind.If_Statement:
                statements.append(self._extract_if_statement(api, statement))
            elif kind == api.nodes.Iir_Kind.Case_Statement:
                statements.append(self._extract_case_statement(api, statement))
            elif kind == api.nodes.Iir_Kind.Null_Statement:
                statements.append(RawNullStatement(source=self._source_from_iir(api, statement)))
            elif kind == api.nodes.Iir_Kind.Wait_Statement:
                self._raise_unsupported(
                    api,
                    statement,
                    "wait 语句不属于当前可综合组合 RTL 子集。",
                    "HDLX-VHDL-WAIT",
                )
            else:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    statement,
                    f"顺序构造 {kind_name} 尚未纳入当前 VHDL 子集。",
                    "HDLX-VHDL-SEQUENTIAL-CONSTRUCT",
                )
        return tuple(statements)

    def _extract_procedural_assignment(
        self, api: SimpleNamespace, statement: Any
    ) -> RawProceduralAssignment:
        value = self._extract_single_waveform_value(
            api, api.nodes.Get_Waveform_Chain(statement), statement
        )
        return RawProceduralAssignment(
            target=self._expression_from_iir(api, api.nodes.Get_Target(statement)),
            value=value,
            source=self._source_from_iir(api, statement),
        )

    def _extract_if_statement(self, api: SimpleNamespace, statement: Any) -> RawIfStatement:
        condition = self._expression_from_iir(api, api.nodes.Get_Condition(statement))
        then_body = self._extract_sequential_chain(
            api, api.nodes.Get_Sequential_Statement_Chain(statement)
        )

        elsif_branches: list[
            tuple[RawExpression, tuple[RawStatement, ...], RawSourceLocation | None]
        ] = []
        else_body: tuple[RawStatement, ...] = ()
        else_clause = api.nodes.Get_Else_Clause(statement)
        while else_clause != api.nodes.Null_Iir:
            branch_condition = api.nodes.Get_Condition(else_clause)
            branch_body = self._extract_sequential_chain(
                api, api.nodes.Get_Sequential_Statement_Chain(else_clause)
            )
            if branch_condition == api.nodes.Null_Iir:
                else_body = branch_body
                break
            elsif_branches.append(
                (
                    self._expression_from_iir(api, branch_condition),
                    branch_body,
                    self._source_from_iir(api, else_clause),
                )
            )
            else_clause = api.nodes.Get_Else_Clause(else_clause)

        for branch_condition, branch_body, branch_source in reversed(elsif_branches):
            else_body = (
                RawIfStatement(
                    condition=branch_condition,
                    then_body=branch_body,
                    else_body=else_body,
                    source=branch_source,
                ),
            )
        return RawIfStatement(
            condition=condition,
            then_body=then_body,
            else_body=else_body,
            source=self._source_from_iir(api, statement),
        )

    def _extract_case_statement(self, api: SimpleNamespace, statement: Any) -> RawCaseStatement:
        expression = self._expression_from_iir(api, api.nodes.Get_Expression(statement))
        alternatives: list[RawCaseAlternative] = []
        default_body: tuple[RawStatement, ...] = ()
        has_default = False
        choice = api.nodes.Get_Case_Statement_Alternative_Chain(statement)
        while choice != api.nodes.Null_Iir:
            kind = api.nodes.Get_Kind(choice)
            if kind == api.nodes.Iir_Kind.Choice_By_Others:
                if has_default:
                    self._raise_unsupported(
                        api,
                        choice,
                        "case 语句包含多个 others 分支。",
                        "HDLX-VHDL-CASE-OTHERS",
                    )
                default_body = self._extract_sequential_chain(
                    api, api.nodes.Get_Associated_Chain(choice)
                )
                has_default = True
                choice = api.nodes.Get_Chain(choice)
                continue
            if kind not in {
                api.nodes.Iir_Kind.Choice_By_Expression,
                api.nodes.Iir_Kind.Choice_By_Name,
            }:
                kind_name = self._enum_name(api.nodes.Iir_Kind, kind)
                self._raise_unsupported(
                    api,
                    choice,
                    f"case 选择类型 {kind_name} 尚未纳入当前子集。",
                    "HDLX-VHDL-CASE-CHOICE",
                )

            head = choice
            selectors = [self._expression_from_iir(api, api.nodes.Get_Choice_Expression(choice))]
            next_choice = api.nodes.Get_Chain(choice)
            while next_choice != api.nodes.Null_Iir and api.nodes.Get_Same_Alternative_Flag(
                next_choice
            ):
                next_kind = api.nodes.Get_Kind(next_choice)
                if next_kind not in {
                    api.nodes.Iir_Kind.Choice_By_Expression,
                    api.nodes.Iir_Kind.Choice_By_Name,
                }:
                    self._raise_unsupported(
                        api,
                        next_choice,
                        "共享 case 分支仅支持离散表达式选择值。",
                        "HDLX-VHDL-CASE-CHOICE",
                    )
                selectors.append(
                    self._expression_from_iir(api, api.nodes.Get_Choice_Expression(next_choice))
                )
                next_choice = api.nodes.Get_Chain(next_choice)

            alternatives.append(
                RawCaseAlternative(
                    selectors=tuple(selectors),
                    body=self._extract_sequential_chain(api, api.nodes.Get_Associated_Chain(head)),
                    source=self._source_from_iir(api, head),
                )
            )
            choice = next_choice

        return RawCaseStatement(
            expression=expression,
            alternatives=tuple(alternatives),
            default_body=default_body,
            source=self._source_from_iir(api, statement),
        )

    def _convert_type(self, api: SimpleNamespace, subtype: Any) -> RawType:
        type_name = self._simple_name(api, subtype.Name, "类型标记")
        normalized_name = type_name.casefold()
        source = self._source_from_dom(subtype)

        if normalized_name in {"std_logic", "std_ulogic"}:
            return RawType(
                kind=RawTypeKind.SCALAR,
                source_name=type_name,
                four_state=True,
                source=source,
            )
        if normalized_name == "bit":
            return RawType(
                kind=RawTypeKind.SCALAR,
                source_name=type_name,
                four_state=False,
                source=source,
            )
        if normalized_name in {"integer", "natural", "positive"}:
            return RawType(
                kind=RawTypeKind.INTEGER,
                source_name=type_name,
                signed=True,
                source=source,
            )
        if normalized_name == "boolean":
            return RawType(
                kind=RawTypeKind.BOOLEAN,
                source_name=type_name,
                source=source,
            )
        if normalized_name in {"std_logic_vector", "std_ulogic_vector", "signed", "unsigned"}:
            constraints = tuple(getattr(subtype, "Constraints", ()))
            if len(constraints) != 1:
                self._raise_unsupported_dom(
                    subtype,
                    f"向量类型 {type_name!r} 必须具有一个显式离散范围。",
                    "HDLX-VHDL-VECTOR-RANGE",
                )
            constraint = constraints[0]
            if isinstance(constraint, api.expression.AscendingRangeExpression):
                direction = RawRangeDirection.TO
            elif isinstance(constraint, api.expression.DescendingRangeExpression):
                direction = RawRangeDirection.DOWNTO
            else:
                self._raise_unsupported_dom(
                    constraint,
                    "只有显式 to/downto 向量范围可安全转换。",
                    "HDLX-VHDL-VECTOR-RANGE",
                )
            raw_range = RawRange(
                left=self._convert_expression(api, constraint.LeftOperand),
                right=self._convert_expression(api, constraint.RightOperand),
                direction=direction,
                source=self._source_from_dom(constraint),
            )
            return RawType(
                kind=RawTypeKind.VECTOR,
                source_name=type_name,
                signed=normalized_name == "signed",
                four_state=True,
                range=raw_range,
                source=source,
            )

        self._raise_unsupported_dom(
            subtype,
            f"VHDL 类型 {type_name!r} 尚未纳入当前 RTL 子集。",
            "HDLX-VHDL-TYPE",
        )

    def _expression_from_iir(self, api: SimpleNamespace, node: Any) -> RawExpression:
        expression = api.translate.GetExpressionFromNode(node)
        return self._convert_expression(api, expression)

    def _convert_expression(self, api: SimpleNamespace, expression: Any) -> RawExpression:
        source = self._source_from_dom(expression)
        literals = api.literal
        expressions = api.expression
        symbols = api.symbol

        if isinstance(expression, literals.IntegerLiteral):
            return RawLiteral(expression.Value, RawLiteralKind.INTEGER, source)
        if isinstance(expression, literals.CharacterLiteral):
            value = expression.Value
            if value.upper() not in {"0", "1", "U", "X", "Z", "W", "L", "H", "-"}:
                self._raise_unsupported_dom(
                    expression,
                    f"字符字面量 {value!r} 不是受支持的逻辑值。",
                    "HDLX-VHDL-LITERAL",
                )
            return RawLiteral(value, RawLiteralKind.BIT, source)
        bit_string_classes = (
            literals.BinaryBitStringLiteral,
            literals.OctalBitStringLiteral,
            literals.HexadecimalBitStringLiteral,
            literals.DecimalBitStringLiteral,
        )
        if isinstance(expression, bit_string_classes):
            return RawLiteral(expression.Value, RawLiteralKind.BIT_VECTOR, source)
        if isinstance(expression, literals.StringLiteral):
            value = expression.Value
            kind = (
                RawLiteralKind.BIT_VECTOR
                if value and all(char.upper() in "01UXZWLH-" for char in value)
                else RawLiteralKind.STRING
            )
            return RawLiteral(value, kind, source)
        if isinstance(expression, literals.EnumerationLiteral):
            value = str(expression.Value)
            if value.casefold() in {"true", "false"}:
                return RawLiteral(value.casefold() == "true", RawLiteralKind.BOOLEAN, source)
            self._raise_unsupported_dom(
                expression,
                f"枚举字面量 {value!r} 尚未纳入当前子集。",
                "HDLX-VHDL-LITERAL",
            )

        if isinstance(expression, symbols.SimpleObjectOrFunctionCallSymbol):
            name = self._simple_name(api, expression.Name, "名称引用")
            if name.casefold() in {"true", "false"}:
                return RawLiteral(name.casefold() == "true", RawLiteralKind.BOOLEAN, source)
            return RawIdentifier(name=name, source=source)
        if isinstance(expression, symbols.IndexedObjectOrFunctionCallSymbol):
            parenthesis_name = expression.Name
            if not isinstance(parenthesis_name, api.name.ParenthesisName):
                self._raise_unsupported_dom(
                    expression,
                    "只有单维索引名称可安全转换。",
                    "HDLX-VHDL-NAME",
                )
            associations = tuple(parenthesis_name.Associations)
            if len(associations) != 1:
                self._raise_unsupported_dom(
                    expression,
                    "多维索引或函数调用尚未纳入当前子集。",
                    "HDLX-VHDL-NAME",
                )
            value = RawIdentifier(
                name=self._simple_name(api, parenthesis_name.Prefix, "索引前缀"),
                source=self._source_from_dom(parenthesis_name.Prefix),
            )
            return RawIndexExpression(
                value=value,
                index=self._convert_expression(api, associations[0]),
                source=source,
            )
        if isinstance(expression, expressions.ParenthesisExpression):
            return self._convert_expression(api, expression.Operand)

        unary_map = {
            expressions.InverseExpression: RawUnaryOperator.NOT,
            expressions.NegationExpression: RawUnaryOperator.NEGATE,
            expressions.IdentityExpression: RawUnaryOperator.POSITIVE,
        }
        for expression_type, operator in unary_map.items():
            if isinstance(expression, expression_type):
                return RawUnaryExpression(
                    operator=operator,
                    operand=self._convert_expression(api, expression.Operand),
                    source=source,
                )

        binary_map = {
            expressions.AdditionExpression: RawBinaryOperator.ADD,
            expressions.SubtractionExpression: RawBinaryOperator.SUBTRACT,
            expressions.MultiplyExpression: RawBinaryOperator.MULTIPLY,
            expressions.DivisionExpression: RawBinaryOperator.DIVIDE,
            expressions.ModuloExpression: RawBinaryOperator.MODULO,
            expressions.ExponentiationExpression: RawBinaryOperator.POWER,
            expressions.AndExpression: RawBinaryOperator.AND,
            expressions.NandExpression: RawBinaryOperator.NAND,
            expressions.OrExpression: RawBinaryOperator.OR,
            expressions.NorExpression: RawBinaryOperator.NOR,
            expressions.XorExpression: RawBinaryOperator.XOR,
            expressions.XnorExpression: RawBinaryOperator.XNOR,
            expressions.EqualExpression: RawBinaryOperator.EQUAL,
            expressions.UnequalExpression: RawBinaryOperator.NOT_EQUAL,
            expressions.LessThanExpression: RawBinaryOperator.LESS_THAN,
            expressions.LessEqualExpression: RawBinaryOperator.LESS_EQUAL,
            expressions.GreaterThanExpression: RawBinaryOperator.GREATER_THAN,
            expressions.GreaterEqualExpression: RawBinaryOperator.GREATER_EQUAL,
            expressions.ConcatenationExpression: RawBinaryOperator.CONCATENATE,
        }
        for expression_type, operator in binary_map.items():
            if isinstance(expression, expression_type):
                return RawBinaryExpression(
                    left=self._convert_expression(api, expression.LeftOperand),
                    operator=operator,
                    right=self._convert_expression(api, expression.RightOperand),
                    source=source,
                )

        self._raise_unsupported_dom(
            expression,
            f"表达式节点 {type(expression).__name__} 尚未纳入当前 VHDL 子集。",
            "HDLX-VHDL-EXPRESSION",
        )

    def _simple_name(self, api: SimpleNamespace, name: Any, role: str) -> str:
        if isinstance(name, api.name.SimpleName):
            return name.Identifier
        self._raise_unsupported_dom(
            name,
            f"{role} {type(name).__name__} 尚未纳入当前 VHDL 子集。",
            "HDLX-VHDL-NAME",
        )

    @staticmethod
    def _label_from_iir(api: SimpleNamespace, node: Any) -> str | None:
        label = api.nodes.Get_Label(node)
        if label == api.nodes.Null_Iir:
            return None
        return str(api.name_table.Get_Name_Ptr(label))

    def _source_from_dom(self, node: Any) -> RawSourceLocation | None:
        try:
            position = node.Position
            return RawSourceLocation(
                file=Path(position.Filename),
                line=int(position.Line),
                column=int(position.Column) + 1,
            )
        except (AttributeError, TypeError, ValueError):
            return None

    def _source_from_iir(
        self,
        api: SimpleNamespace,
        node: Any,
    ) -> RawSourceLocation | None:
        try:
            position = api.Position.parse(node)
            start_line = int(position.Line)
            start_column = int(position.Column) + 1
            end = self._end_from_iir(api, node, start_line, start_column)
            return RawSourceLocation(
                file=Path(position.Filename),
                line=start_line,
                column=start_column,
                end_line=end[0] if end is not None else None,
                end_column=end[1] if end is not None else None,
            )
        except (AttributeError, TypeError, ValueError, OSError):
            return None

    def _end_from_iir(
        self,
        api: SimpleNamespace,
        node: Any,
        start_line: int,
        start_column: int,
    ) -> tuple[int, int] | None:
        """只对已验证 getter 或简单分号节点提取半开结束位置。"""

        kind = api.nodes.Get_Kind(node)
        structural_kinds = {
            api.nodes.Iir_Kind.Architecture_Body: "architecture",
            api.nodes.Iir_Kind.Entity_Declaration: "entity",
            api.nodes.Iir_Kind.Component_Declaration: "component",
            api.nodes.Iir_Kind.Process_Statement: "process",
            api.nodes.Iir_Kind.Sensitized_Process_Statement: "process",
            api.nodes.Iir_Kind.If_Generate_Statement: "generate",
            api.nodes.Iir_Kind.For_Generate_Statement: "generate",
            api.nodes.Iir_Kind.Block_Statement: "block",
        }
        semicolon_kinds = {
            api.nodes.Iir_Kind.Signal_Declaration,
            api.nodes.Iir_Kind.Component_Instantiation_Statement,
            api.nodes.Iir_Kind.Simple_Signal_Assignment_Statement,
            api.nodes.Iir_Kind.Concurrent_Simple_Signal_Assignment,
            api.nodes.Iir_Kind.Concurrent_Conditional_Signal_Assignment,
            api.nodes.Iir_Kind.Null_Statement,
        }

        if kind in structural_kinds:
            return self._scan_to_end_clause(
                start_line,
                start_column,
                structural_kinds[kind],
            )
        if kind in semicolon_kinds:
            return self._scan_to_semicolon(start_line, start_column)
        return None

    def _scan_to_semicolon(self, line: int, column: int) -> tuple[int, int] | None:
        """从 GHDL 锚点扫描最近语句分号，不解析 VHDL grammar。"""

        lines = getattr(self, "_active_source_lines", ())
        in_string = False
        for line_index in range(line - 1, len(lines)):
            text = lines[line_index]
            index = column - 1 if line_index == line - 1 else 0
            while index < len(text):
                character = text[index]
                if character == '"':
                    if in_string and index + 1 < len(text) and text[index + 1] == '"':
                        index += 2
                        continue
                    in_string = not in_string
                elif not in_string and character == "-" and text[index : index + 2] == "--":
                    break
                elif not in_string and character == ";":
                    return line_index + 1, index + 2
                index += 1
        return None

    def _scan_to_end_clause(
        self,
        line: int,
        column: int,
        keyword: str,
    ) -> tuple[int, int] | None:
        """扫描已由 IIR 分类节点的结束子句，并处理嵌套 generate。"""

        identifier = r"[A-Za-z][A-Za-z0-9_]*"
        end_pattern = re.compile(
            rf"\bend\s+(?:postponed\s+)?{keyword}(?:\s+{identifier})?\s*;",
            re.IGNORECASE,
        )
        open_pattern = re.compile(rf"\b{keyword}\b", re.IGNORECASE)
        lines = getattr(self, "_active_source_lines", ())
        depth = 0
        for line_index in range(line - 1, len(lines)):
            text = self._mask_non_code(lines[line_index])
            start = column - 1 if line_index == line - 1 else 0
            if keyword != "generate":
                match = end_pattern.search(text, start)
                if match is not None:
                    return line_index + 1, match.end() + 1
                continue

            token_pattern = re.compile(
                rf"{end_pattern.pattern}|{open_pattern.pattern}",
                re.IGNORECASE,
            )
            for match in token_pattern.finditer(text, start):
                if end_pattern.fullmatch(match.group(0)):
                    depth -= 1
                    if depth <= 0:
                        return line_index + 1, match.end() + 1
                else:
                    depth += 1
        return None

    @staticmethod
    def _mask_non_code(text: str) -> str:
        """保留列宽并屏蔽字符串与行注释，供窄 span 扫描使用。"""

        characters = list(text)
        in_string = False
        index = 0
        while index < len(characters):
            if characters[index] == '"':
                characters[index] = " "
                if in_string and index + 1 < len(characters) and characters[index + 1] == '"':
                    characters[index + 1] = " "
                    index += 2
                    continue
                in_string = not in_string
            elif in_string:
                characters[index] = " "
            elif characters[index] == "-" and text[index : index + 2] == "--":
                return "".join(characters[:index]) + " " * (len(characters) - index)
            index += 1
        return "".join(characters)

    def _raise_unsupported(
        self,
        api: SimpleNamespace,
        node: Any,
        message: str,
        code: str,
    ) -> None:
        source = self._source_from_iir(api, node)
        self._raise_unsupported_at(source, message, code)

    def _raise_unsupported_dom(self, node: Any, message: str, code: str) -> None:
        source = self._source_from_dom(node)
        self._raise_unsupported_at(source, message, code)

    @staticmethod
    def _raise_unsupported_at(source: RawSourceLocation | None, message: str, code: str) -> None:
        raise UnsupportedConstructError(
            message,
            code=code,
            file=str(source.file) if source is not None else None,
            line=source.line if source is not None else None,
            column=source.column if source is not None else None,
        )

    @staticmethod
    def _format_ghdl_error(error: BaseException) -> str:
        messages: list[str] = []
        current: BaseException | None = error
        while current is not None:
            text = str(current).strip()
            if text and text not in messages:
                messages.append(text)
            internal_errors = getattr(current, "InternalErrors", None)
            if internal_errors:
                for item in internal_errors:
                    item_text = str(item).strip()
                    if item_text and item_text not in messages:
                        messages.append(item_text)
            current = current.__cause__
        return "; ".join(messages) or type(error).__name__

    @staticmethod
    def _error_location(details: str) -> tuple[int | None, int | None]:
        """将 libghdl 的 0-based 行内 offset 转成 canonical 1-based 列号。"""

        match = re.search(r"(?<!\d):(\d+):(\d+):", details)
        if match is None:
            return None, None
        return int(match.group(1)), int(match.group(2)) + 1

    @staticmethod
    def _enum_name(enum_type: Any, value: Any) -> str:
        try:
            return enum_type(value).name
        except (TypeError, ValueError):
            return str(value)


__all__ = ["PyGhdlBackend"]
