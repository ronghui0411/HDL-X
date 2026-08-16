"""Canonical IR 语义转换。"""

from .identifier_resolver import DesignIdentifierResolver, IdentifierResolver, NameStyle
from .semantic_lowering import SemanticLowering

__all__ = [
    "DesignIdentifierResolver",
    "IdentifierResolver",
    "NameStyle",
    "SemanticLowering",
]
