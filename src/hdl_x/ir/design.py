"""Canonical RTL 设计容器。"""

from __future__ import annotations

from typing import Literal as TypingLiteral

from pydantic import Field, model_validator

from .base import IRNode
from .module import Module


class Design(IRNode):
    """一个或多个保持层次关系的 canonical 设计单元。"""

    kind: TypingLiteral["design"] = "design"
    name: str | None = None
    modules: list[Module] = Field(min_length=1)
    top: str | None = None

    @model_validator(mode="after")
    def validate_modules(self) -> Design:
        module_names = [module.name for module in self.modules]
        if len(module_names) != len(set(module_names)):
            raise ValueError("design module names must be unique")
        if self.top is not None and self.top not in module_names:
            raise ValueError("design top must reference a contained module")
        return self
