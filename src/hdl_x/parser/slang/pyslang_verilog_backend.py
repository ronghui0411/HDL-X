"""基于 pyslang 11.0.0 的 Verilog-2001 frontend profile。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hdl_x.diagnostics import HDLXError, UnsupportedConstructError

from .pyslang_backend import PySlangBackend
from .raw import RawSystemVerilogDesign

_UNSUPPORTED_VERILOG_SYNTAX: dict[str, tuple[str, str]] = {
    "InterfaceDeclaration": ("HDLX-V2V-INTERFACE", "interface 不是 Verilog-2001 构造"),
    "ProgramDeclaration": ("HDLX-V2V-PROGRAM", "program 不在可综合 Verilog MVP 内"),
    "PackageDeclaration": ("HDLX-V2V-PACKAGE", "package 不在 Verilog-2001 MVP 内"),
    "ClassDeclaration": ("HDLX-V2V-CLASS", "class 不在可综合 Verilog MVP 内"),
    "ClockingDeclaration": ("HDLX-V2V-CLOCKING", "clocking block 不在 MVP 内"),
    "InitialBlock": ("HDLX-V2V-INITIAL", "initial block 不在可综合 MVP 内"),
    "FinalBlock": ("HDLX-V2V-FINAL", "final block 不在可综合 MVP 内"),
    "AlwaysCombBlock": ("HDLX-V2V-SYSTEMVERILOG", "always_comb 不是 Verilog-2001 构造"),
    "AlwaysFFBlock": ("HDLX-V2V-SYSTEMVERILOG", "always_ff 不是 Verilog-2001 构造"),
    "AlwaysLatchBlock": ("HDLX-V2V-SYSTEMVERILOG", "always_latch 不是 Verilog-2001 构造"),
    "FunctionDeclaration": ("HDLX-V2V-FUNCTION", "function declaration 暂不在 v0.3 MVP 内"),
    "TaskDeclaration": ("HDLX-V2V-TASK", "task declaration 暂不在 v0.3 MVP 内"),
    "TypedefDeclaration": ("HDLX-V2V-TYPEDEF", "typedef 不是 Verilog-2001 MVP 构造"),
    "CaseGenerate": ("HDLX-V2V-GENERATE", "case generate 不在初始 v0.3 MVP 内"),
    "BindDirective": ("HDLX-V2V-BIND", "bind 不是受支持的 Verilog-2001 RTL"),
    "WaitStatement": ("HDLX-V2V-WAIT", "wait statement 不在可综合 MVP 内"),
    "ForkJoinBlock": ("HDLX-V2V-FORK", "fork/join 不在可综合 MVP 内"),
    "ImmediateAssertionStatement": ("HDLX-V2V-ASSERTION", "assertion 不在可综合 MVP 内"),
    "ImmediateAssertStatement": ("HDLX-V2V-ASSERTION", "assertion 不在可综合 MVP 内"),
    "ConcurrentAssertionMember": ("HDLX-V2V-ASSERTION", "assertion 不在可综合 MVP 内"),
}


class PySlangVerilogBackend(PySlangBackend):
    """允许 Verilog ``always``，并把诊断稳定映射到 V2V 命名空间。"""

    def parse(self, source_path: Path) -> RawSystemVerilogDesign:
        try:
            return super().parse(source_path)
        except HDLXError as error:
            diagnostic = error.diagnostic
            code = diagnostic.code
            if code.startswith("HDLX-SV-"):
                code = f"HDLX-V2V-{code.removeprefix('HDLX-SV-')}"
            message = diagnostic.message.replace("SystemVerilog", "Verilog-2001").replace(
                "v0.2", "v0.3"
            )
            raise type(error)(
                diagnostic=diagnostic.model_copy(update={"code": code, "message": message})
            ) from error

    def _raise_diagnostic(
        self,
        diagnostic: Any,
        *,
        pyslang: Any,
        source_manager: Any,
        source_path: Path,
    ) -> None:
        diagnostic_code = str(diagnostic.code)
        if diagnostic_code in {
            "DiagCode(ArithOpMismatch)",
            "DiagCode(WidthTruncate)",
        }:
            span = self._location_span(
                diagnostic.location,
                source_manager,
                source_path,
            )
            raise UnsupportedConstructError(
                "Slang 检测到隐式 operand/target 位宽转换；当前 V2V MVP "
                "不猜测 Verilog sizing、截断或 VHDL resize 的等价性",
                code="HDLX-V2V-SIZING",
                source_span=span,
                source_snippet=self._source_line(source_path, span.start.line),
                suggestion="将 operands 与 target 改为相同显式位宽和 signedness。",
            )
        if diagnostic_code == "DiagCode(UnnamedGenerate)":
            span = self._location_span(
                diagnostic.location,
                source_manager,
                source_path,
            )
            raise UnsupportedConstructError(
                "generate block 必须有显式 label 才能稳定保留层次",
                code="HDLX-V2V-GENERATE-LABEL",
                source_span=span,
                source_snippet=self._source_line(source_path, span.start.line),
                suggestion="为 generate begin/end block 添加显式名称。",
            )
        super()._raise_diagnostic(
            diagnostic,
            pyslang=pyslang,
            source_manager=source_manager,
            source_path=source_path,
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
            if kind in _UNSUPPORTED_VERILOG_SYNTAX and hasattr(node, "sourceRange"):
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
        code, message = _UNSUPPORTED_VERILOG_SYNTAX[node.kind.name]
        span = self._source_span(node.sourceRange, source_manager, source_path)
        raise UnsupportedConstructError(
            message,
            code=code,
            source_span=span,
            source_snippet=self._source_line(source_path, span.start.line),
            suggestion="移除该构造，或等待 v0.3 支持矩阵明确扩展。",
        )


__all__ = ["PySlangVerilogBackend"]
