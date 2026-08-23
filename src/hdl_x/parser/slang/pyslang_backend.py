"""基于 pyslang 11.0.0 的真实 SystemVerilog frontend backend。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hdl_x.diagnostics import FrontendError, UnsupportedConstructError
from hdl_x.ir import SourceLocation, SourceSpan

from .base import SlangFrontendBackend
from .raw import RawSourceSpan, RawSystemVerilogDesign, RawSystemVerilogModule
from .runtime import require_pyslang_runtime

_UNSUPPORTED_SYNTAX: dict[str, tuple[str, str]] = {
    "InterfaceDeclaration": ("HDLX-SV-INTERFACE", "SystemVerilog interface 不在 v0.2 MVP 内"),
    "ModportDeclaration": ("HDLX-SV-MODPORT", "SystemVerilog modport 不在 v0.2 MVP 内"),
    "ProgramDeclaration": ("HDLX-SV-PROGRAM", "SystemVerilog program 不在可综合 MVP 内"),
    "PackageDeclaration": ("HDLX-SV-PACKAGE", "SystemVerilog package 不在 v0.2 MVP 内"),
    "ClassDeclaration": ("HDLX-SV-CLASS", "SystemVerilog class 不在可综合 MVP 内"),
    "ClockingDeclaration": ("HDLX-SV-CLOCKING", "clocking block 不在可综合 MVP 内"),
    "InitialBlock": ("HDLX-SV-INITIAL", "initial block 不在可综合 MVP 内"),
    "FinalBlock": ("HDLX-SV-FINAL", "final block 不在可综合 MVP 内"),
    "AlwaysLatchBlock": ("HDLX-SV-ALWAYS-LATCH", "always_latch 不在 v0.2 MVP 内"),
    "AlwaysBlock": ("HDLX-SV-ALWAYS", "普通 always 不在 v0.2 MVP 内；使用 always_comb/always_ff"),
    "FunctionDeclaration": ("HDLX-SV-FUNCTION", "function declaration 不在 v0.2 MVP 内"),
    "TaskDeclaration": ("HDLX-SV-TASK", "task declaration 不在 v0.2 MVP 内"),
    "TypedefDeclaration": ("HDLX-SV-TYPEDEF", "typedef/复杂类型不在 v0.2 MVP 内"),
    "GenerateRegion": ("HDLX-SV-GENERATE", "SystemVerilog generate 不在首个 v0.2 切片内"),
    "LoopGenerate": ("HDLX-SV-GENERATE", "SystemVerilog generate 不在首个 v0.2 切片内"),
    "IfGenerate": ("HDLX-SV-GENERATE", "SystemVerilog generate 不在首个 v0.2 切片内"),
    "CaseGenerate": ("HDLX-SV-GENERATE", "SystemVerilog generate 不在首个 v0.2 切片内"),
    "BindDirective": ("HDLX-SV-BIND", "bind directive 不在 v0.2 MVP 内"),
    "WaitStatement": ("HDLX-SV-WAIT", "wait statement 不在可综合 MVP 内"),
    "ForkJoinBlock": ("HDLX-SV-FORK", "fork/join 不在可综合 MVP 内"),
    "ImmediateAssertionStatement": ("HDLX-SV-ASSERTION", "assertion 不在可综合 MVP 内"),
    "ImmediateAssertStatement": ("HDLX-SV-ASSERTION", "assertion 不在可综合 MVP 内"),
    "ConcurrentAssertionMember": ("HDLX-SV-ASSERTION", "assertion 不在可综合 MVP 内"),
}


class PySlangBackend(SlangFrontendBackend):
    """调用真实 Slang parse/compilation，并立即隔离所有 pyslang 对象。"""

    def parse(self, source_path: Path) -> RawSystemVerilogDesign:
        path = Path(source_path).resolve()
        if not path.is_file():
            raise FrontendError(
                f"SystemVerilog 源文件不存在：{path}",
                code="HDLX-SV-SOURCE-NOT-FOUND",
                file=str(path),
            )

        pyslang = require_pyslang_runtime()
        source_manager = pyslang.SourceManager()
        try:
            syntax_tree = pyslang.syntax.SyntaxTree.fromFile(str(path), source_manager)
            compilation = pyslang.ast.Compilation()
            compilation.addSyntaxTree(syntax_tree)
            diagnostics = tuple(compilation.getAllDiagnostics())
        except (OSError, RuntimeError, ValueError) as error:
            raise FrontendError(
                f"Slang 无法分析 {path.name}：{error}",
                code="HDLX-SV-FRONTEND",
                file=str(path),
            ) from error

        self._reject_include_directives(
            syntax_tree,
            source_manager=source_manager,
            source_path=path,
        )

        if diagnostics:
            self._raise_diagnostic(
                diagnostics[0],
                pyslang=pyslang,
                source_manager=source_manager,
                source_path=path,
            )

        self._reject_unsupported_syntax(
            syntax_tree.root,
            source_manager=source_manager,
            source_path=path,
        )
        self._reject_cross_file_syntax(
            syntax_tree.root,
            source_manager=source_manager,
            source_path=path,
        )

        syntax_modules = self._module_nodes(syntax_tree.root)
        if not syntax_modules:
            raise UnsupportedConstructError(
                "输入不包含可转换的 SystemVerilog module",
                code="HDLX-SV-NO-MODULE",
                file=str(path),
            )

        modules: list[RawSystemVerilogModule] = []
        for node in syntax_modules:
            payload = json.loads(node.to_json())
            if not isinstance(payload, dict):
                raise FrontendError(
                    "Slang module serialization 未返回对象",
                    code="HDLX-SV-SERIALIZATION",
                    source_span=self._source_span(node.sourceRange, source_manager, path),
                )
            modules.append(
                RawSystemVerilogModule(
                    name=node.header.name.valueText,
                    syntax=payload,
                    source=self._raw_span(node.sourceRange, source_manager, path),
                )
            )

        root = compilation.getRoot()
        top_names = tuple(instance.name for instance in root.topInstances if instance.isModule)
        return RawSystemVerilogDesign(
            source_path=path,
            modules=tuple(modules),
            top_names=top_names,
        )

    def _raise_diagnostic(
        self,
        diagnostic: Any,
        *,
        pyslang: Any,
        source_manager: Any,
        source_path: Path,
    ) -> None:
        engine = pyslang.DiagnosticEngine(source_manager)
        message = engine.formatMessage(diagnostic)
        location = diagnostic.location
        span = self._location_span(location, source_manager, source_path)
        if str(diagnostic.code) == "DiagCode(SignConversion)":
            raise UnsupportedConstructError(
                f"Slang 检出 signedness conversion，目标 sizing 无法保证等价：{message}",
                code="HDLX-SV-SIGNED-SIZING",
                source_span=span,
                source_snippet=self._source_line(source_path, span.start.line),
                suggestion="使用 signedness 与位宽一致的操作数，或显式重写表达式后重试。",
            )
        code = "HDLX-SV-SYNTAX" if diagnostic.isError() else "HDLX-SV-DIAGNOSTIC"
        raise FrontendError(
            f"Slang 诊断 {diagnostic.code}: {message}",
            code=code,
            source_span=span,
            source_snippet=self._source_line(source_path, span.start.line),
            suggestion="修正 Slang 报告的 SystemVerilog 问题后重试。",
        )

    def _reject_unsupported_syntax(
        self,
        root: Any,
        *,
        source_manager: Any,
        source_path: Path,
    ) -> None:
        matches: list[Any] = []

        def collect(node: Any) -> None:
            kind = getattr(getattr(node, "kind", None), "name", None)
            if kind in _UNSUPPORTED_SYNTAX and hasattr(node, "sourceRange"):
                matches.append(node)

        root.visit(collect)
        if not matches:
            return
        matches.sort(
            key=lambda node: (
                source_manager.getLineNumber(node.sourceRange.start),
                source_manager.getColumnNumber(node.sourceRange.start),
            )
        )
        node = matches[0]
        kind = node.kind.name
        code, message = _UNSUPPORTED_SYNTAX[kind]
        span = self._source_span(node.sourceRange, source_manager, source_path)
        raise UnsupportedConstructError(
            message,
            code=code,
            source_span=span,
            source_snippet=self._source_line(source_path, span.start.line),
            suggestion="移除该构造，或等待 HDL-X 扩展明确支持范围。",
        )

    def _reject_include_directives(
        self,
        syntax_tree: Any,
        *,
        source_manager: Any,
        source_path: Path,
    ) -> None:
        directives = tuple(syntax_tree.getIncludeDirectives())
        if not directives:
            return
        directive = min(
            directives,
            key=lambda item: (
                source_manager.getLineNumber(item.syntax.sourceRange.start),
                source_manager.getColumnNumber(item.syntax.sourceRange.start),
            ),
        )
        span = self._source_span(
            directive.syntax.sourceRange,
            source_manager,
            source_path,
        )
        raise UnsupportedConstructError(
            f"跨文件 include {directive.path!r} 不在 v0.2 单文件 MVP 内",
            code="HDLX-SV-COMPILATION-UNIT",
            source_span=span,
            source_snippet=self._source_line(source_path, span.start.line),
            suggestion="移除 include 并使用单文件受支持子集，或等待多文件支持。",
        )

    def _reject_cross_file_syntax(
        self,
        root: Any,
        *,
        source_manager: Any,
        source_path: Path,
    ) -> None:
        matches: list[Any] = []

        def collect(node: Any) -> None:
            source_range = getattr(node, "sourceRange", None)
            if source_range is not None and source_manager.isIncludedFileLoc(source_range.start):
                matches.append(node)

        root.visit(collect)
        if not matches:
            return
        matches.sort(
            key=lambda node: (
                str(source_manager.getFileName(node.sourceRange.start)),
                source_manager.getLineNumber(node.sourceRange.start),
                source_manager.getColumnNumber(node.sourceRange.start),
            )
        )
        node = matches[0]
        included_path = Path(str(source_manager.getFileName(node.sourceRange.start))).resolve()
        span = self._source_span(node.sourceRange, source_manager, included_path)
        raise UnsupportedConstructError(
            "跨文件 include/compilation-unit 语义不在 v0.2 MVP 内",
            code="HDLX-SV-COMPILATION-UNIT",
            source_span=span,
            source_snippet=self._source_line(included_path, span.start.line),
            suggestion="将设计整理为单文件受支持子集，或等待多 compilation-unit 支持。",
        )

    @staticmethod
    def _module_nodes(root: Any) -> tuple[Any, ...]:
        if getattr(root.kind, "name", None) == "ModuleDeclaration":
            return (root,)
        if getattr(root.kind, "name", None) != "CompilationUnit":
            return ()
        return tuple(
            node
            for node in root.members
            if getattr(getattr(node, "kind", None), "name", None) == "ModuleDeclaration"
        )

    @classmethod
    def _source_span(
        cls,
        source_range: Any,
        source_manager: Any,
        source_path: Path,
    ) -> SourceSpan:
        raw = cls._raw_span(source_range, source_manager, source_path)
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
    def _raw_span(
        source_range: Any,
        source_manager: Any,
        source_path: Path,
    ) -> RawSourceSpan:
        return RawSourceSpan(
            file=source_path,
            start_line=source_manager.getLineNumber(source_range.start),
            start_column=source_manager.getColumnNumber(source_range.start),
            end_line=source_manager.getLineNumber(source_range.end),
            end_column=source_manager.getColumnNumber(source_range.end),
        )

    @classmethod
    def _location_span(
        cls,
        location: Any,
        source_manager: Any,
        source_path: Path,
    ) -> SourceSpan:
        line = source_manager.getLineNumber(location)
        column = source_manager.getColumnNumber(location)
        point = SourceLocation(file=str(source_path), line=line, column=column)
        return SourceSpan(start=point, end=point.model_copy())

    @staticmethod
    def _source_line(source_path: Path, line: int) -> str | None:
        try:
            lines = source_path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            return None
        if 1 <= line <= len(lines):
            return lines[line - 1]
        return None


__all__ = ["PySlangBackend"]
