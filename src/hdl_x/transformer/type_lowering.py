"""面向 Verilog-2001 声明需求的 driver analysis。"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from hdl_x.diagnostics import SemanticError
from hdl_x.ir import (
    AssignmentKind,
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    Concatenation,
    ContinuousAssignment,
    Design,
    DriverKind,
    ForGenerate,
    ForStatement,
    Identifier,
    IfGenerate,
    IfStatement,
    Index,
    Instance,
    IntegerType,
    Module,
    NullStatement,
    Port,
    PortDirection,
    ProceduralAssignment,
    SequentialProcess,
    Signal,
    Slice,
    Variable,
)

from .semantic_lowering import SemanticLowering

Declaration = Port | Signal | Variable


@dataclass
class _DriverEvidence:
    declaration: Declaration
    continuous_sites: set[_DriverSite] = field(default_factory=set)
    procedural_processes: set[_DriverSite] = field(default_factory=set)


@dataclass(frozen=True)
class _DriverSite:
    """驱动来源及其所在的 elaboration 条件路径。"""

    identity: int
    choices: frozenset[tuple[int, bool]] = frozenset()


@dataclass(frozen=True)
class _RepeatedGenerate:
    """for-generate 复制上下文及其每次迭代独立的局部声明。"""

    index_name: str
    local_declarations: frozenset[int]


class DriverAnalysis(SemanticLowering):
    """分析 canonical assignment/instance 关系并标注 net/variable 驱动语义。"""

    def lower(self, design: Design) -> Design:
        """返回深拷贝，避免 generator 修改调用方持有的 canonical IR。"""

        lowered = design.model_copy(deep=True)
        modules = {module.name: module for module in lowered.modules}
        evidence: dict[int, _DriverEvidence] = {}

        for module in lowered.modules:
            symbols: dict[str, Declaration] = {}
            declarations: list[Declaration] = [
                *module.ports,
                *module.signals,
                *module.variables,
            ]
            for declaration in declarations:
                if declaration.name in symbols:
                    raise SemanticError(
                        f"duplicate declaration {declaration.name!r}",
                        code="HDLX-DRIVER-DUPLICATE",
                        source_span=declaration.source_span,
                    )
                symbols[declaration.name] = declaration
                evidence[id(declaration)] = _DriverEvidence(declaration)

            self._walk_region(
                module.items,
                symbols,
                modules,
                evidence,
                allow_shadowing=False,
                choices=frozenset(),
                repeated_indices=(),
            )

        for item in evidence.values():
            self._apply_driver_kind(item)
        return lowered

    def _walk_region(
        self,
        items: Sequence[object],
        inherited_symbols: dict[str, Declaration],
        modules: dict[str, Module],
        evidence: dict[int, _DriverEvidence],
        *,
        allow_shadowing: bool,
        choices: frozenset[tuple[int, bool]],
        repeated_indices: tuple[_RepeatedGenerate, ...],
    ) -> None:
        symbols = dict(inherited_symbols)
        local_names: set[str] = set()
        for item in items:
            if not isinstance(item, Signal | Variable):
                continue
            if item.name in local_names or (not allow_shadowing and item.name in inherited_symbols):
                raise SemanticError(
                    f"duplicate declaration {item.name!r}",
                    code="HDLX-DRIVER-DUPLICATE",
                    source_span=item.source_span,
                )
            local_names.add(item.name)
            symbols[item.name] = item
            evidence[id(item)] = _DriverEvidence(item)

        for item in items:
            if isinstance(item, ContinuousAssignment):
                self._validate_generate_target(item.target, repeated_indices, symbols)
                self._record_target(
                    item.target,
                    DriverKind.CONTINUOUS,
                    symbols,
                    evidence,
                    site=_DriverSite(id(item), choices),
                )
            elif isinstance(item, CombinationalProcess | SequentialProcess):
                self._walk_process(
                    item,
                    symbols,
                    evidence,
                    site=_DriverSite(id(item), choices),
                    repeated_indices=repeated_indices,
                )
            elif isinstance(item, Instance):
                self._walk_instance(
                    item,
                    symbols,
                    modules,
                    evidence,
                    choices=choices,
                    repeated_indices=repeated_indices,
                )
            elif isinstance(item, ForGenerate):
                self._walk_region(
                    item.body,
                    symbols,
                    modules,
                    evidence,
                    allow_shadowing=True,
                    choices=choices,
                    repeated_indices=(
                        *repeated_indices,
                        _RepeatedGenerate(
                            item.index_name,
                            self._collect_local_declaration_ids(item.body),
                        ),
                    ),
                )
            elif isinstance(item, IfGenerate):
                self._walk_region(
                    item.then_body,
                    symbols,
                    modules,
                    evidence,
                    allow_shadowing=True,
                    choices=choices | {(id(item), True)},
                    repeated_indices=repeated_indices,
                )
                self._walk_region(
                    item.else_body,
                    symbols,
                    modules,
                    evidence,
                    allow_shadowing=True,
                    choices=choices | {(id(item), False)},
                    repeated_indices=repeated_indices,
                )

    def _walk_process(
        self,
        process: CombinationalProcess | SequentialProcess,
        symbols: dict[str, Declaration],
        evidence: dict[int, _DriverEvidence],
        *,
        site: _DriverSite,
        repeated_indices: tuple[_RepeatedGenerate, ...],
    ) -> None:
        if isinstance(process, SequentialProcess):
            self._walk_statements(
                process.reset_body,
                symbols,
                evidence,
                process=process,
                site=site,
                repeated_indices=repeated_indices,
            )
        self._walk_statements(
            process.body,
            symbols,
            evidence,
            process=process,
            site=site,
            repeated_indices=repeated_indices,
        )

    def _walk_statements(
        self,
        statements: Sequence[object],
        symbols: dict[str, Declaration],
        evidence: dict[int, _DriverEvidence],
        *,
        process: CombinationalProcess | SequentialProcess,
        site: _DriverSite,
        repeated_indices: tuple[_RepeatedGenerate, ...],
    ) -> None:
        for statement in statements:
            if isinstance(statement, ProceduralAssignment):
                self._validate_generate_target(statement.target, repeated_indices, symbols)
                declarations = self._record_target(
                    statement.target,
                    DriverKind.PROCEDURAL,
                    symbols,
                    evidence,
                    site=site,
                )
                self._validate_procedural_assignment(statement, declarations, process)
            elif isinstance(statement, ContinuousAssignment):
                raise SemanticError(
                    "continuous assignment cannot appear inside a process",
                    code="HDLX-DRIVER-CONTINUOUS-IN-PROCESS",
                    source_span=statement.source_span,
                )
            elif isinstance(statement, IfStatement):
                self._walk_statements(
                    statement.then_body,
                    symbols,
                    evidence,
                    process=process,
                    site=site,
                    repeated_indices=repeated_indices,
                )
                self._walk_statements(
                    statement.else_body,
                    symbols,
                    evidence,
                    process=process,
                    site=site,
                    repeated_indices=repeated_indices,
                )
            elif isinstance(statement, CaseStatement):
                for alternative in statement.alternatives:
                    self._walk_statements(
                        alternative.body,
                        symbols,
                        evidence,
                        process=process,
                        site=site,
                        repeated_indices=repeated_indices,
                    )
                self._walk_statements(
                    statement.default_body,
                    symbols,
                    evidence,
                    process=process,
                    site=site,
                    repeated_indices=repeated_indices,
                )
            elif isinstance(statement, ForStatement):
                loop_variable = symbols.get(statement.index_name)
                if not isinstance(loop_variable, Variable) or not isinstance(
                    loop_variable.rtl_type, IntegerType
                ):
                    raise SemanticError(
                        f"procedural loop index {statement.index_name!r} requires an "
                        "explicit IntegerType Variable",
                        code="HDLX-LOOP-INDEX-DECLARATION",
                        source_span=statement.source_span,
                    )
                self._walk_statements(
                    statement.body,
                    symbols,
                    evidence,
                    process=process,
                    site=site,
                    repeated_indices=repeated_indices,
                )
            elif isinstance(statement, BlockStatement):
                self._walk_statements(
                    statement.statements,
                    symbols,
                    evidence,
                    process=process,
                    site=site,
                    repeated_indices=repeated_indices,
                )
            elif isinstance(statement, NullStatement):
                continue

    def _walk_instance(
        self,
        instance: Instance,
        symbols: dict[str, Declaration],
        modules: dict[str, Module],
        evidence: dict[int, _DriverEvidence],
        *,
        choices: frozenset[tuple[int, bool]],
        repeated_indices: tuple[_RepeatedGenerate, ...],
    ) -> None:
        referenced = modules.get(instance.referenced_unit)
        if referenced is None:
            # 外部 black-box 的端口方向未知，不能猜测它是否驱动 actual。
            return

        named_parameters = {parameter.name: parameter for parameter in referenced.parameters}
        for parameter_binding in instance.parameter_bindings:
            if parameter_binding.formal is not None:
                if parameter_binding.formal not in named_parameters:
                    raise SemanticError(
                        f"instance {instance.name!r} binds unknown parameter "
                        f"{parameter_binding.formal!r}",
                        code="HDLX-INSTANCE-UNKNOWN-PARAMETER",
                        source_span=parameter_binding.source_span or instance.source_span,
                    )
            else:
                assert parameter_binding.position is not None
                if parameter_binding.position >= len(referenced.parameters):
                    raise SemanticError(
                        f"instance {instance.name!r} parameter position is out of range",
                        code="HDLX-INSTANCE-PARAMETER-RANGE",
                        source_span=parameter_binding.source_span or instance.source_span,
                    )

        named_ports = {port.name: port for port in referenced.ports}
        for port_binding in instance.port_bindings:
            if port_binding.formal is not None:
                port = named_ports.get(port_binding.formal)
                if port is None:
                    raise SemanticError(
                        f"instance {instance.name!r} binds unknown port {port_binding.formal!r}",
                        code="HDLX-INSTANCE-UNKNOWN-PORT",
                        source_span=port_binding.source_span or instance.source_span,
                    )
            else:
                assert port_binding.position is not None
                if port_binding.position >= len(referenced.ports):
                    raise SemanticError(
                        f"instance {instance.name!r} port position is out of range",
                        code="HDLX-INSTANCE-PORT-RANGE",
                        source_span=port_binding.source_span or instance.source_span,
                    )
                port = referenced.ports[port_binding.position]

            if (
                port.direction in (PortDirection.OUTPUT, PortDirection.INOUT)
                and port_binding.value is not None
            ):
                self._validate_generate_target(port_binding.value, repeated_indices, symbols)
                self._record_target(
                    port_binding.value,
                    DriverKind.CONTINUOUS,
                    symbols,
                    evidence,
                    site=_DriverSite(id(port_binding), choices),
                )

    def _record_target(
        self,
        target: object,
        kind: DriverKind,
        symbols: dict[str, Declaration],
        evidence: dict[int, _DriverEvidence],
        *,
        site: _DriverSite,
    ) -> list[Declaration]:
        if isinstance(target, Identifier):
            declaration = symbols.get(target.name)
            if declaration is None:
                raise SemanticError(
                    f"assignment target {target.name!r} is not declared",
                    code="HDLX-DRIVER-UNDECLARED",
                    source_span=target.source_span,
                )
            item = evidence[id(declaration)]
            if kind is DriverKind.CONTINUOUS:
                item.continuous_sites.add(site)
            else:
                item.procedural_processes.add(site)
            return [declaration]
        if isinstance(target, Index | Slice):
            return self._record_target(target.value, kind, symbols, evidence, site=site)
        if isinstance(target, Concatenation):
            declarations: dict[int, Declaration] = {}
            for part in target.parts:
                for declaration in self._record_target(part, kind, symbols, evidence, site=site):
                    declarations[id(declaration)] = declaration
            return list(declarations.values())
        raise SemanticError(
            f"expression {type(target).__name__} is not an assignable target",
            code="HDLX-DRIVER-NON-LVALUE",
            source_span=getattr(target, "source_span", None),
        )

    def _validate_generate_target(
        self,
        target: object,
        repeated_indices: tuple[_RepeatedGenerate, ...],
        symbols: dict[str, Declaration],
    ) -> None:
        for repeated in repeated_indices:
            if not self._target_is_partitioned_by(
                target,
                repeated.index_name,
                repeated.local_declarations,
                symbols,
            ):
                raise SemanticError(
                    f"driver replicated by generate index {repeated.index_name!r} does not "
                    "partition its assignment target",
                    code="HDLX-DRIVER-GENERATE-TARGET",
                    source_span=getattr(target, "source_span", None),
                )

    def _target_is_partitioned_by(
        self,
        target: object,
        index_name: str,
        local_declarations: frozenset[int],
        symbols: dict[str, Declaration],
    ) -> bool:
        if isinstance(target, Identifier):
            declaration = symbols.get(target.name)
            return declaration is not None and id(declaration) in local_declarations
        if isinstance(target, Index):
            if isinstance(target.index, Identifier) and target.index.name == index_name:
                return True
            return self._target_is_partitioned_by(
                target.value, index_name, local_declarations, symbols
            )
        if isinstance(target, Slice):
            return self._target_is_partitioned_by(
                target.value, index_name, local_declarations, symbols
            )
        if isinstance(target, Concatenation):
            return all(
                self._target_is_partitioned_by(part, index_name, local_declarations, symbols)
                for part in target.parts
            )
        return False

    def _collect_local_declaration_ids(self, items: Sequence[object]) -> frozenset[int]:
        declarations: set[int] = set()
        for item in items:
            if isinstance(item, Signal | Variable):
                declarations.add(id(item))
            elif isinstance(item, ForGenerate):
                declarations.update(self._collect_local_declaration_ids(item.body))
            elif isinstance(item, IfGenerate):
                declarations.update(self._collect_local_declaration_ids(item.then_body))
                declarations.update(self._collect_local_declaration_ids(item.else_body))
        return frozenset(declarations)

    def _validate_procedural_assignment(
        self,
        assignment: ProceduralAssignment,
        declarations: list[Declaration],
        process: CombinationalProcess | SequentialProcess,
    ) -> None:
        if isinstance(process, CombinationalProcess):
            if assignment.assignment_kind is not AssignmentKind.BLOCKING:
                raise SemanticError(
                    "combinational process assignments must use blocking semantics",
                    code="HDLX-ASSIGNMENT-COMB-NONBLOCKING",
                    source_span=assignment.source_span,
                )
            return

        for declaration in declarations:
            if isinstance(declaration, Variable):
                if assignment.assignment_kind is not AssignmentKind.BLOCKING:
                    raise SemanticError(
                        f"sequential-process variable {declaration.name!r} must use "
                        "blocking semantics",
                        code="HDLX-ASSIGNMENT-VARIABLE-NONBLOCKING",
                        source_span=assignment.source_span,
                    )
            elif assignment.assignment_kind is not AssignmentKind.NON_BLOCKING:
                raise SemanticError(
                    f"sequential-process signal {declaration.name!r} must use "
                    "non-blocking semantics",
                    code="HDLX-ASSIGNMENT-SIGNAL-BLOCKING",
                    source_span=assignment.source_span,
                )

    def _apply_driver_kind(self, evidence: _DriverEvidence) -> None:
        declaration = evidence.declaration
        if evidence.continuous_sites and evidence.procedural_processes:
            raise SemanticError(
                f"{declaration.name!r} has mixed continuous and procedural drivers",
                code="HDLX-DRIVER-MIXED",
                source_span=declaration.source_span,
            )

        if self._has_coexisting_sites(evidence.continuous_sites):
            raise SemanticError(
                f"{declaration.name!r} has multiple continuous driver sites",
                code="HDLX-DRIVER-MULTIPLE-CONTINUOUS",
                source_span=declaration.source_span,
            )
        if self._has_coexisting_sites(evidence.procedural_processes):
            raise SemanticError(
                f"{declaration.name!r} is driven by multiple independent processes",
                code="HDLX-DRIVER-MULTIPLE-PROCESSES",
                source_span=declaration.source_span,
            )

        if evidence.continuous_sites:
            inferred = DriverKind.CONTINUOUS
        elif evidence.procedural_processes:
            inferred = DriverKind.PROCEDURAL
        else:
            inferred = None
        if isinstance(declaration, Variable):
            if inferred is DriverKind.CONTINUOUS:
                raise SemanticError(
                    f"variable {declaration.name!r} cannot have a continuous driver",
                    code="HDLX-DRIVER-VARIABLE-CONTINUOUS",
                    source_span=declaration.source_span,
                )
            return

        if isinstance(declaration, Port):
            if declaration.direction is PortDirection.INPUT and inferred is not None:
                raise SemanticError(
                    f"input port {declaration.name!r} is driven internally",
                    code="HDLX-DRIVER-INPUT",
                    source_span=declaration.source_span,
                )
            if declaration.direction is PortDirection.INOUT and inferred is DriverKind.PROCEDURAL:
                raise SemanticError(
                    f"inout port {declaration.name!r} requires net semantics",
                    code="HDLX-DRIVER-INOUT-PROCEDURAL",
                    source_span=declaration.source_span,
                )

        if isinstance(declaration.rtl_type, IntegerType) and inferred is DriverKind.CONTINUOUS:
            raise SemanticError(
                f"integer object {declaration.name!r} cannot have a continuous driver",
                code="HDLX-DRIVER-INTEGER-CONTINUOUS",
                source_span=declaration.source_span,
            )

        explicit = declaration.driver_kind
        if explicit is not None and inferred is not None and explicit is not inferred:
            raise SemanticError(
                f"driver annotation for {declaration.name!r} conflicts with assignments",
                code="HDLX-DRIVER-ANNOTATION-CONFLICT",
                source_span=declaration.source_span,
            )
        if explicit is not None:
            return
        if inferred is not None:
            declaration.driver_kind = inferred
        else:
            declaration.driver_kind = DriverKind.CONTINUOUS

    @staticmethod
    def _has_coexisting_sites(sites: set[_DriverSite]) -> bool:
        ordered = list(sites)
        for index, left in enumerate(ordered):
            left_choices = dict(left.choices)
            for right in ordered[index + 1 :]:
                right_choices = dict(right.choices)
                mutually_exclusive = any(
                    choice in right_choices and right_choices[choice] is not value
                    for choice, value in left_choices.items()
                )
                if not mutually_exclusive:
                    return True
        return False
