"""源 HDL frontend 抽象。"""

from .base import Frontend
from .comments import (
    SystemVerilogCommentScanner,
    VhdlCommentScanner,
    scan_systemverilog_comments,
    scan_vhdl_comments,
)
from .systemverilog import SystemVerilogFrontend
from .vhdl import VhdlFrontend

__all__ = [
    "Frontend",
    "SystemVerilogFrontend",
    "SystemVerilogCommentScanner",
    "VhdlCommentScanner",
    "VhdlFrontend",
    "scan_systemverilog_comments",
    "scan_vhdl_comments",
]
