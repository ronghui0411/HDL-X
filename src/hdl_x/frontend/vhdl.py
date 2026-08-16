"""VHDL frontend 的稳定组合入口。"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from pathlib import Path

from hdl_x.frontend.base import Frontend
from hdl_x.frontend.comments import (
    associate_comments_by_source_span,
    scan_vhdl_comments,
)
from hdl_x.ir import (
    BlockStatement,
    CaseStatement,
    CombinationalProcess,
    Comment,
    Design,
    ForGenerate,
    ForStatement,
    IfGenerate,
    IfStatement,
    Instance,
    IRNode,
    ModuleItem,
    SequentialProcess,
    StatementNode,
)
from hdl_x.parser.ghdl import GhdlFrontendBackend, PyGhdlBackend, RawDesign
from hdl_x.parser.vhdl_adapter import VhdlAdapter


class VhdlFrontend(Frontend[RawDesign]):
    """组合可替换的 GHDL backend 与 canonical IR adapter。"""

    def __init__(
        self,
        backend: GhdlFrontendBackend | None = None,
        adapter: VhdlAdapter | None = None,
    ) -> None:
        self._backend = backend or PyGhdlBackend()
        self._adapter = adapter or VhdlAdapter()
        self._unassociated_comments: tuple[Comment, ...] = ()

    @property
    def backend(self) -> GhdlFrontendBackend:
        """返回当前使用的 GHDL backend。"""

        return self._backend

    @property
    def adapter(self) -> VhdlAdapter:
        """返回 frontend 私有表示适配器。"""

        return self._adapter

    @property
    def unassociated_comments(self) -> tuple[Comment, ...]:
        """返回上次解析中无法安全关联的非致命源码注释。"""

        return self._unassociated_comments

    def parse(self, source_path: Path) -> RawDesign:
        return self._backend.parse(source_path)

    def parse_design(self, source_path: Path) -> Design:
        """解析并转换为 canonical Design，供 pipeline 直接组合。"""

        path = Path(source_path).resolve()
        self._unassociated_comments = ()
        design = self._adapter.adapt(self.parse(path))
        source = path.read_text(encoding="utf-8-sig")
        nodes = list(_iter_commentable_nodes(design))
        association = associate_comments_by_source_span(
            scan_vhdl_comments(source, file=path),
            nodes,
            source=source,
        )
        for item in association.associations:
            node = nodes[item.node_index]
            _extend_unique(node.leading_comments, item.leading_comments)
            _extend_unique(node.trailing_comments, item.trailing_comments)
        self._unassociated_comments = association.unassociated_comments
        return design


def _iter_commentable_nodes(design: Design) -> Iterator[IRNode]:
    """按源码结构顺序遍历 generator 能实际呈现注释的节点。"""

    for module in design.modules:
        yield module
        yield from module.parameters
        yield from module.ports
        yield from module.signals
        yield from module.variables
        yield from _iter_module_items(module.items)


def _iter_module_items(items: Sequence[ModuleItem]) -> Iterator[IRNode]:
    for item in items:
        yield item
        if isinstance(item, Instance):
            yield from item.parameter_bindings
            yield from item.port_bindings
        elif isinstance(item, CombinationalProcess):
            yield from _iter_statements(item.body)
        elif isinstance(item, SequentialProcess):
            yield from _iter_statements(item.reset_body)
            yield from _iter_statements(item.body)
        elif isinstance(item, ForGenerate):
            yield from _iter_module_items(item.body)
        elif isinstance(item, IfGenerate):
            yield from _iter_module_items(item.then_body)
            yield from _iter_module_items(item.else_body)


def _iter_statements(statements: Sequence[StatementNode]) -> Iterator[IRNode]:
    for statement in statements:
        yield statement
        if isinstance(statement, IfStatement):
            yield from _iter_statements(statement.then_body)
            yield from _iter_statements(statement.else_body)
        elif isinstance(statement, CaseStatement):
            for alternative in statement.alternatives:
                yield from _iter_statements(alternative.body)
            yield from _iter_statements(statement.default_body)
        elif isinstance(statement, ForStatement):
            yield from _iter_statements(statement.body)
        elif isinstance(statement, BlockStatement):
            yield from _iter_statements(statement.statements)


def _extend_unique(target: list[Comment], comments: Sequence[Comment]) -> None:
    """保持扫描顺序，并避免同一 canonical 注释被重复附着。"""

    for comment in comments:
        if comment not in target:
            target.append(comment)


__all__ = ["VhdlFrontend"]
