"""源 HDL frontend 抽象。"""

from .base import Frontend
from .comments import VhdlCommentScanner, scan_vhdl_comments
from .vhdl import VhdlFrontend

__all__ = ["Frontend", "VhdlCommentScanner", "VhdlFrontend", "scan_vhdl_comments"]
