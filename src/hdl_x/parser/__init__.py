"""Frontend 表示到 canonical IR 的适配层。"""

from .base import ParserAdapter
from .systemverilog_adapter import SystemVerilogAdapter
from .vhdl_adapter import VhdlAdapter

__all__ = ["ParserAdapter", "SystemVerilogAdapter", "VhdlAdapter"]
