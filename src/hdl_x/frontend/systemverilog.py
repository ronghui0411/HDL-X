"""SystemVerilog frontend 的稳定 Slang + adapter 组合入口。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from hdl_x.frontend.base import Frontend
from hdl_x.frontend.comments import (
    associate_comments_by_source_span,
    scan_systemverilog_comments,
)
from hdl_x.ir import Comment, Design
from hdl_x.parser.slang import (
    PySlangBackend,
    RawSystemVerilogDesign,
    SlangFrontendBackend,
)
from hdl_x.parser.systemverilog_adapter import SystemVerilogAdapter


class SystemVerilogFrontend(Frontend[RawSystemVerilogDesign]):
    """组合真实 Slang backend 与 language-neutral Canonical adapter。"""

    def __init__(
        self,
        backend: SlangFrontendBackend | None = None,
        adapter: SystemVerilogAdapter | None = None,
    ) -> None:
        self._backend = backend or PySlangBackend()
        self._adapter = adapter or SystemVerilogAdapter()
        self._unassociated_comments: tuple[Comment, ...] = ()

    @property
    def backend(self) -> SlangFrontendBackend:
        return self._backend

    @property
    def adapter(self) -> SystemVerilogAdapter:
        return self._adapter

    @property
    def unassociated_comments(self) -> tuple[Comment, ...]:
        """返回上次解析中无法安全关联的非致命源码注释。"""

        return self._unassociated_comments

    def parse(self, source_path: Path) -> RawSystemVerilogDesign:
        return self._backend.parse(Path(source_path))

    def parse_design(self, source_path: Path) -> Design:
        path = Path(source_path).resolve()
        self._unassociated_comments = ()
        design = self._adapter.adapt(self.parse(path))
        source = path.read_text(encoding="utf-8-sig")
        modules = list(design.modules)
        association = associate_comments_by_source_span(
            scan_systemverilog_comments(source, file=path),
            modules,
            source=source,
            standalone_comment_prefixes=("//", "/*", "*", "*/"),
        )
        for item in association.associations:
            module = modules[item.node_index]
            _extend_unique(module.leading_comments, item.leading_comments)
            _extend_unique(module.trailing_comments, item.trailing_comments)
        self._unassociated_comments = association.unassociated_comments
        return design


def _extend_unique(target: list[Comment], comments: Sequence[Comment]) -> None:
    """保持扫描顺序，并避免同一 canonical 注释被重复附着。"""

    for comment in comments:
        if comment not in target:
            target.append(comment)


__all__ = ["SystemVerilogFrontend"]
