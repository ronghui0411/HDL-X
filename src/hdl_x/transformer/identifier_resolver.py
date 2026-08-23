"""跨语言标识符解析与碰撞消解。"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from hdl_x.diagnostics import SemanticError
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
    FunctionCall,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Instance,
    IRNode,
    Literal,
    Module,
    NullStatement,
    ProceduralAssignment,
    SequentialProcess,
    Signal,
    Slice,
    SourceSpan,
    TernaryExpr,
    UnaryExpr,
    Variable,
    VectorRange,
    VectorType,
)

from .semantic_lowering import SemanticLowering


class NameStyle(str, Enum):
    """可选名称样式。"""

    PRESERVE = "preserve"
    SNAKE_CASE = "snake_case"
    CAMEL_CASE = "camelCase"
    PASCAL_CASE = "PascalCase"


VERILOG_2001_KEYWORDS = frozenset(
    {
        "always",
        "and",
        "assign",
        "automatic",
        "begin",
        "buf",
        "bufif0",
        "bufif1",
        "case",
        "casex",
        "casez",
        "cell",
        "cmos",
        "config",
        "deassign",
        "default",
        "defparam",
        "design",
        "disable",
        "edge",
        "else",
        "end",
        "endcase",
        "endconfig",
        "endfunction",
        "endgenerate",
        "endmodule",
        "endprimitive",
        "endspecify",
        "endtable",
        "endtask",
        "event",
        "for",
        "force",
        "forever",
        "fork",
        "function",
        "generate",
        "genvar",
        "highz0",
        "highz1",
        "if",
        "ifnone",
        "incdir",
        "include",
        "initial",
        "inout",
        "input",
        "instance",
        "integer",
        "join",
        "large",
        "liblist",
        "library",
        "localparam",
        "macromodule",
        "medium",
        "module",
        "nand",
        "negedge",
        "nmos",
        "nor",
        "noshowcancelled",
        "not",
        "notif0",
        "notif1",
        "or",
        "output",
        "parameter",
        "pmos",
        "posedge",
        "primitive",
        "pull0",
        "pull1",
        "pulldown",
        "pullup",
        "pulsestyle_ondetect",
        "pulsestyle_onevent",
        "rcmos",
        "real",
        "realtime",
        "reg",
        "release",
        "repeat",
        "rnmos",
        "rpmos",
        "rtran",
        "rtranif0",
        "rtranif1",
        "scalared",
        "showcancelled",
        "signed",
        "small",
        "specify",
        "specparam",
        "strong0",
        "strong1",
        "supply0",
        "supply1",
        "table",
        "task",
        "time",
        "tran",
        "tranif0",
        "tranif1",
        "tri",
        "tri0",
        "tri1",
        "triand",
        "trior",
        "trireg",
        "unsigned",
        "use",
        "vectored",
        "wait",
        "wand",
        "weak0",
        "weak1",
        "while",
        "wire",
        "wor",
        "xnor",
        "xor",
    }
)


class IdentifierResolver:
    """把源名称确定性映射为合法且唯一的 Verilog-2001 名称。"""

    def __init__(
        self,
        style: NameStyle = NameStyle.PRESERVE,
        *,
        case_sensitive: bool = False,
    ) -> None:
        self.style = style
        self.case_sensitive = case_sensitive
        self._source_to_target: dict[str, str] = {}
        self._used_targets: set[str] = set()

    @property
    def mappings(self) -> dict[str, str]:
        """返回映射副本，防止外部破坏解析状态。"""

        return dict(self._source_to_target)

    def resolve(self, source_name: str) -> str:
        """按配置的源语言大小写规则解析名称。"""

        key = self.key(source_name)
        if key in self._source_to_target:
            return self._source_to_target[key]

        candidate = self._allocate(source_name)
        self._source_to_target[key] = candidate
        return candidate

    def resolve_unique(self, source_name: str) -> str:
        """为独立 declaration 分配新名称，即使源拼写曾出现过。"""

        return self._allocate(source_name)

    def reserve_target(self, target_name: str) -> None:
        """将外部 allocator 已分配的目标名称加入当前碰撞集合。"""

        self._used_targets.add(target_name)

    def key(self, source_name: str) -> str:
        return source_name if self.case_sensitive else source_name.casefold()

    def _allocate(self, source_name: str) -> str:
        styled = self._apply_style(source_name)
        candidate = re.sub(r"[^A-Za-z0-9_$]", "_", styled)
        if not candidate or not re.match(r"[A-Za-z_]", candidate):
            candidate = f"hdl_x_{candidate}"
        if candidate in VERILOG_2001_KEYWORDS:
            candidate = f"{candidate}_hdl_x"

        base = candidate
        suffix = 2
        while candidate in self._used_targets:
            candidate = f"{base}_{suffix}"
            suffix += 1

        self._used_targets.add(candidate)
        return candidate

    def _apply_style(self, name: str) -> str:
        if self.style is NameStyle.PRESERVE:
            return name

        words = [part for part in re.split(r"[_\s]+|(?<=[a-z0-9])(?=[A-Z])", name) if part]
        if not words:
            return name
        lowered = [word.lower() for word in words]
        if self.style is NameStyle.SNAKE_CASE:
            return "_".join(lowered)
        if self.style is NameStyle.CAMEL_CASE:
            return lowered[0] + "".join(word.capitalize() for word in lowered[1:])
        return "".join(word.capitalize() for word in lowered)


class _NameScope:
    """保存一个 lexical scope 内的声明及其父级查找关系。"""

    def __init__(
        self,
        style: NameStyle,
        parent: _NameScope | None = None,
        *,
        case_sensitive: bool = False,
    ) -> None:
        self.parent = parent
        self.case_sensitive = case_sensitive
        self.resolver = IdentifierResolver(style, case_sensitive=case_sensitive)
        self.declarations: dict[str, str] = {}

    def declare(self, source_name: str, *, source_span: SourceSpan | None = None) -> str:
        key = self.resolver.key(source_name)
        if key in self.declarations:
            mode = "case-sensitive" if self.case_sensitive else "case-insensitive"
            raise SemanticError(
                f"duplicate {mode} declaration {source_name!r}",
                code="HDLX-NAME-DUPLICATE",
                source_span=source_span,
            )
        generated = self.resolver.resolve(source_name)
        self.declarations[key] = generated
        return generated

    def resolve(self, source_name: str) -> str:
        key = self.resolver.key(source_name)
        scope: _NameScope | None = self
        while scope is not None:
            if key in scope.declarations:
                return scope.declarations[key]
            scope = scope.parent
        return self.resolver.resolve(source_name)

    def resolve_declared(
        self,
        source_name: str,
        *,
        source_span: SourceSpan | None = None,
    ) -> str:
        """解析对象引用；未在当前或父作用域声明时结构化失败。"""

        key = self.resolver.key(source_name)
        scope: _NameScope | None = self
        while scope is not None:
            if key in scope.declarations:
                return scope.declarations[key]
            scope = scope.parent
        raise SemanticError(
            f"unresolved identifier {source_name!r}",
            code="HDLX-NAME-UNRESOLVED",
            source_span=source_span,
        )

    def bind(
        self,
        source_name: str,
        generated_name: str,
        *,
        source_span: SourceSpan | None = None,
    ) -> None:
        """绑定由上级 allocator 分配、但在当前 lexical scope 可见的名称。"""

        key = self.resolver.key(source_name)
        if key in self.declarations:
            mode = "case-sensitive" if self.case_sensitive else "case-insensitive"
            raise SemanticError(
                f"duplicate {mode} declaration {source_name!r}",
                code="HDLX-NAME-DUPLICATE",
                source_span=source_span,
            )
        self.declarations[key] = generated_name
        self.resolver.reserve_target(generated_name)


@dataclass
class _ModuleNames:
    module: Module
    original_name: str
    generated_name: str
    scope: _NameScope
    parameters: dict[str, str]
    ports: dict[str, str]


class DesignIdentifierResolver(SemanticLowering):
    """按 VHDL 大小写规则遍历 Design，并生成合法 Verilog 名称。"""

    def __init__(
        self,
        style: NameStyle = NameStyle.PRESERVE,
        *,
        case_sensitive: bool = False,
    ) -> None:
        self.style = style
        self.case_sensitive = case_sensitive
        self._mappings: dict[str, str] = {}
        self._external_formal_scopes: dict[tuple[str, str], _NameScope] = {}

    @property
    def mappings(self) -> dict[str, str]:
        """返回带作用域路径的 original-name 到 generated-name 映射。"""

        return dict(self._mappings)

    def lower(self, design: Design) -> Design:
        """在深拷贝上解析所有声明、引用、关联 formal 与层次名称。"""

        self._mappings = {}
        self._external_formal_scopes = {}
        resolved = design.model_copy(deep=True)
        global_scope = _NameScope(self.style, case_sensitive=self.case_sensitive)
        modules: dict[str, _ModuleNames] = {}

        for module in resolved.modules:
            original = module.name
            generated = global_scope.declare(original, source_span=module.source_span)
            self._mappings[f"module::{original}"] = generated
            scope = _NameScope(self.style, case_sensitive=self.case_sensitive)
            parameters: dict[str, str] = {}
            ports: dict[str, str] = {}
            for parameter in module.parameters:
                parameters[self._key(parameter.name)] = self._declare(
                    scope,
                    parameter.name,
                    f"{original}::parameter::{parameter.name}",
                    parameter,
                )
            for port in module.ports:
                ports[self._key(port.name)] = self._declare(
                    scope,
                    port.name,
                    f"{original}::port::{port.name}",
                    port,
                )
            for signal in module.signals:
                self._declare(
                    scope,
                    signal.name,
                    f"{original}::object::{signal.name}",
                    signal,
                )
            for variable in module.variables:
                self._declare(
                    scope,
                    variable.name,
                    f"{original}::object::{variable.name}",
                    variable,
                )
            self._declare_items(module.items, scope, original)
            modules[self._key(original)] = _ModuleNames(
                module=module,
                original_name=original,
                generated_name=generated,
                scope=scope,
                parameters=parameters,
                ports=ports,
            )

        for module_names in modules.values():
            self._rewrite_module(module_names, modules, global_scope)

        if resolved.top is not None:
            top_record = modules.get(self._key(resolved.top))
            resolved.top = (
                top_record.generated_name
                if top_record is not None
                else global_scope.resolve(resolved.top)
            )
        return resolved

    def _key(self, name: str) -> str:
        return name if self.case_sensitive else name.casefold()

    def _declare(
        self,
        scope: _NameScope,
        name: str,
        path: str,
        node: IRNode,
    ) -> str:
        generated = scope.declare(name, source_span=getattr(node, "source_span", None))
        self._mappings[path] = generated
        return generated

    def _declare_items(self, items: Sequence[object], scope: _NameScope, path: str) -> None:
        for item in items:
            if isinstance(item, Signal | Variable):
                category = "signal" if isinstance(item, Signal) else "variable"
                self._declare(scope, item.name, f"{path}::{category}::{item.name}", item)
            elif isinstance(item, Instance):
                self._declare(scope, item.name, f"{path}::instance::{item.name}", item)
            elif isinstance(item, ForGenerate | IfGenerate):
                self._declare(scope, item.label, f"{path}::generate::{item.label}", item)
            elif isinstance(item, CombinationalProcess | SequentialProcess) and item.label:
                self._declare(scope, item.label, f"{path}::process::{item.label}", item)

    def _rewrite_module(
        self,
        record: _ModuleNames,
        modules: dict[str, _ModuleNames],
        global_scope: _NameScope,
    ) -> None:
        module = record.module
        scope = record.scope
        module.name = record.generated_name
        for parameter in module.parameters:
            self._rewrite_type(parameter.rtl_type, scope)
            if parameter.default is not None:
                self._rewrite_expression(parameter.default, scope)
            parameter.name = scope.resolve(parameter.name)
        for port in module.ports:
            self._rewrite_type(port.rtl_type, scope)
            port.name = scope.resolve(port.name)
        for signal in module.signals:
            self._rewrite_declaration(signal, scope)
        for variable in module.variables:
            self._rewrite_declaration(variable, scope)
        self._rewrite_items(
            module.items,
            scope,
            modules,
            global_scope,
            record.original_name,
            genvar_resolver=scope.resolver,
        )

    def _rewrite_items(
        self,
        items: Sequence[object],
        scope: _NameScope,
        modules: dict[str, _ModuleNames],
        global_scope: _NameScope,
        path: str,
        *,
        genvar_resolver: IdentifierResolver,
    ) -> None:
        for item in items:
            if isinstance(item, Signal | Variable):
                self._rewrite_declaration(item, scope)
            elif isinstance(item, ContinuousAssignment):
                self._rewrite_expression(item.target, scope)
                self._rewrite_expression(item.value, scope)
            elif isinstance(item, CombinationalProcess | SequentialProcess):
                if item.label is not None:
                    item.label = scope.resolve(item.label)
                if isinstance(item, SequentialProcess):
                    self._rewrite_expression(item.clock, scope)
                    if item.reset is not None:
                        self._rewrite_expression(item.reset.signal, scope)
                    self._rewrite_statements(item.reset_body, scope)
                else:
                    for expression in item.sensitivity:
                        self._rewrite_expression(expression, scope)
                self._rewrite_statements(item.body, scope)
            elif isinstance(item, Instance):
                original_unit = item.referenced_unit
                target = modules.get(self._key(original_unit))
                item.referenced_unit = (
                    target.generated_name
                    if target is not None
                    else global_scope.resolve(original_unit)
                )
                item.name = scope.resolve(item.name)
                for parameter_binding in item.parameter_bindings:
                    self._rewrite_expression(parameter_binding.value, scope)
                    if parameter_binding.formal is not None:
                        parameter_binding.formal = self._resolve_formal(
                            parameter_binding.formal,
                            target,
                            item.referenced_unit,
                            "parameter",
                        )
                for port_binding in item.port_bindings:
                    if port_binding.value is not None:
                        self._rewrite_expression(port_binding.value, scope)
                    if port_binding.formal is not None:
                        port_binding.formal = self._resolve_formal(
                            port_binding.formal,
                            target,
                            item.referenced_unit,
                            "port",
                        )
            elif isinstance(item, ForGenerate):
                original_label = item.label
                original_index = item.index_name
                item.label = scope.resolve(original_label)
                self._rewrite_range(item.range, scope)
                child = _NameScope(
                    self.style,
                    scope,
                    case_sensitive=self.case_sensitive,
                )
                item.index_name = genvar_resolver.resolve_unique(original_index)
                child.bind(
                    original_index,
                    item.index_name,
                    source_span=item.source_span,
                )
                self._mappings[f"{path}::generate::{original_label}::index::{original_index}"] = (
                    item.index_name
                )
                self._declare_items(item.body, child, f"{path}::{original_label}")
                self._rewrite_items(
                    item.body,
                    child,
                    modules,
                    global_scope,
                    f"{path}::{original_label}",
                    genvar_resolver=genvar_resolver,
                )
            elif isinstance(item, IfGenerate):
                original_label = item.label
                item.label = scope.resolve(original_label)
                self._rewrite_expression(item.condition, scope)
                for branch_name, branch in (
                    ("then", item.then_body),
                    ("else", item.else_body),
                ):
                    child = _NameScope(
                        self.style,
                        scope,
                        case_sensitive=self.case_sensitive,
                    )
                    branch_path = f"{path}::{original_label}::{branch_name}"
                    self._declare_items(branch, child, branch_path)
                    self._rewrite_items(
                        branch,
                        child,
                        modules,
                        global_scope,
                        branch_path,
                        genvar_resolver=genvar_resolver,
                    )

    def _resolve_formal(
        self,
        formal: str,
        target: _ModuleNames | None,
        generated_unit: str,
        category: str,
    ) -> str:
        if target is not None:
            mapping = target.parameters if category == "parameter" else target.ports
            known = mapping.get(self._key(formal))
            if known is not None:
                return known
            return target.scope.resolve(formal)
        key = (generated_unit, category)
        scope = self._external_formal_scopes.setdefault(
            key,
            _NameScope(self.style, case_sensitive=self.case_sensitive),
        )
        return scope.resolve(formal)

    def _rewrite_declaration(self, declaration: Signal | Variable, scope: _NameScope) -> None:
        self._rewrite_type(declaration.rtl_type, scope)
        if declaration.initial_value is not None:
            self._rewrite_expression(declaration.initial_value, scope)
        declaration.name = scope.resolve(declaration.name)

    def _rewrite_type(self, rtl_type: object, scope: _NameScope) -> None:
        if isinstance(rtl_type, VectorType):
            self._rewrite_range(rtl_type.range, scope)

    def _rewrite_range(self, value: VectorRange, scope: _NameScope) -> None:
        if not isinstance(value.left, int):
            self._rewrite_expression(value.left, scope)
        if not isinstance(value.right, int):
            self._rewrite_expression(value.right, scope)

    def _rewrite_statements(self, statements: Sequence[object], scope: _NameScope) -> None:
        for statement in statements:
            if isinstance(statement, ProceduralAssignment | ContinuousAssignment):
                self._rewrite_expression(statement.target, scope)
                self._rewrite_expression(statement.value, scope)
            elif isinstance(statement, IfStatement):
                self._rewrite_expression(statement.condition, scope)
                self._rewrite_statements(statement.then_body, scope)
                self._rewrite_statements(statement.else_body, scope)
            elif isinstance(statement, CaseStatement):
                self._rewrite_expression(statement.expression, scope)
                for alternative in statement.alternatives:
                    for selector in alternative.selectors:
                        self._rewrite_expression(selector, scope)
                    self._rewrite_statements(alternative.body, scope)
                self._rewrite_statements(statement.default_body, scope)
            elif isinstance(statement, ForStatement):
                statement.index_name = scope.resolve(statement.index_name)
                self._rewrite_range(statement.range, scope)
                self._rewrite_statements(statement.body, scope)
            elif isinstance(statement, BlockStatement):
                if statement.label is not None:
                    statement.label = scope.resolve(statement.label)
                self._rewrite_statements(statement.statements, scope)
            elif isinstance(statement, NullStatement):
                continue

    def _rewrite_expression(self, expression: object, scope: _NameScope) -> None:
        if isinstance(expression, Identifier):
            expression.name = scope.resolve_declared(
                expression.name,
                source_span=expression.source_span,
            )
        elif isinstance(expression, Literal):
            return
        elif isinstance(expression, UnaryExpr):
            self._rewrite_expression(expression.operand, scope)
        elif isinstance(expression, BinaryExpr):
            self._rewrite_expression(expression.left, scope)
            self._rewrite_expression(expression.right, scope)
        elif isinstance(expression, TernaryExpr):
            self._rewrite_expression(expression.condition, scope)
            self._rewrite_expression(expression.when_true, scope)
            self._rewrite_expression(expression.when_false, scope)
        elif isinstance(expression, Concatenation):
            for part in expression.parts:
                self._rewrite_expression(part, scope)
        elif isinstance(expression, Index):
            self._rewrite_expression(expression.value, scope)
            self._rewrite_expression(expression.index, scope)
        elif isinstance(expression, Slice):
            self._rewrite_expression(expression.value, scope)
            self._rewrite_expression(expression.left, scope)
            self._rewrite_expression(expression.right, scope)
        elif isinstance(expression, FunctionCall):
            # canonical IR 可表示由外部编译单元提供的 Verilog function；其
            # 参数仍必须是当前 lexical scope 中可解析的对象引用。
            expression.function.name = scope.resolve(expression.function.name)
            for argument in expression.arguments:
                self._rewrite_expression(argument, scope)
