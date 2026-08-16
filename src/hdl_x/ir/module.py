"""Canonical RTL 设计单元、实例和 generate 层次。"""

from __future__ import annotations

from enum import Enum
from typing import Annotated
from typing import Literal as TypingLiteral

from pydantic import Field, field_validator, model_validator

from .base import IRNode
from .expressions import ExpressionNode
from .statements import (
    CombinationalProcess,
    ContinuousAssignment,
    SequentialProcess,
)
from .types import RTLTypeNode, VectorRange


class PortDirection(str, Enum):
    """模块接口方向。"""

    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"


class DriverKind(str, Enum):
    """driver analysis 为 generator 提供的驱动类别。"""

    CONTINUOUS = "continuous"
    PROCEDURAL = "procedural"


class Parameter(IRNode):
    """可覆盖的设计参数。"""

    kind: TypingLiteral["parameter"] = "parameter"
    name: str = Field(min_length=1)
    rtl_type: RTLTypeNode
    default: ExpressionNode | None = None


class Port(IRNode):
    """模块公开端口。"""

    kind: TypingLiteral["port"] = "port"
    name: str = Field(min_length=1)
    direction: PortDirection
    rtl_type: RTLTypeNode
    driver_kind: DriverKind | None = None


class Signal(IRNode):
    """模块或 generate 作用域内的信号。"""

    kind: TypingLiteral["signal"] = "signal"
    name: str = Field(min_length=1)
    rtl_type: RTLTypeNode
    initial_value: ExpressionNode | None = None
    driver_kind: DriverKind | None = None


class Variable(IRNode):
    """过程或局部作用域中的变量。"""

    kind: TypingLiteral["variable"] = "variable"
    name: str = Field(min_length=1)
    rtl_type: RTLTypeNode
    initial_value: ExpressionNode | None = None


def _validate_association_selector(formal: str | None, position: int | None) -> None:
    if (formal is None) == (position is None):
        raise ValueError("association requires exactly one of formal or position")


class ParameterBinding(IRNode):
    """实例参数的命名或位置关联。"""

    kind: TypingLiteral["parameter_binding"] = "parameter_binding"
    formal: str | None = None
    position: int | None = Field(default=None, ge=0)
    value: ExpressionNode

    @model_validator(mode="after")
    def validate_selector(self) -> ParameterBinding:
        _validate_association_selector(self.formal, self.position)
        return self


class PortBinding(IRNode):
    """实例端口关联；``None`` 表示显式未连接。"""

    kind: TypingLiteral["port_binding"] = "port_binding"
    formal: str | None = None
    position: int | None = Field(default=None, ge=0)
    value: ExpressionNode | None = None

    @model_validator(mode="after")
    def validate_selector(self) -> PortBinding:
        _validate_association_selector(self.formal, self.position)
        return self


class Instance(IRNode):
    """保持名称与连接方式的层次化实例。"""

    kind: TypingLiteral["instance"] = "instance"
    referenced_unit: str = Field(min_length=1)
    name: str = Field(min_length=1)
    parameter_bindings: list[ParameterBinding] = Field(default_factory=list)
    port_bindings: list[PortBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_bindings(self) -> Instance:
        for bindings, label in (
            (self.parameter_bindings, "parameter"),
            (self.port_bindings, "port"),
        ):
            formals = [binding.formal for binding in bindings if binding.formal is not None]
            positions = [
                binding.position for binding in bindings if binding.position is not None
            ]
            if len(formals) != len(set(formals)):
                raise ValueError(f"duplicate named {label} binding")
            if len(positions) != len(set(positions)):
                raise ValueError(f"duplicate positional {label} binding")
            if formals and positions:
                raise ValueError(f"cannot mix named and positional {label} bindings")
        return self


class ForGenerate(IRNode):
    """保持 label 与迭代范围的 generate 层次。"""

    kind: TypingLiteral["for_generate"] = "for_generate"
    label: str = Field(min_length=1)
    index_name: str = Field(min_length=1)
    range: VectorRange
    body: list[ModuleItem] = Field(default_factory=list)


class IfGenerate(IRNode):
    """条件 generate 及其可选 else 层次。"""

    kind: TypingLiteral["if_generate"] = "if_generate"
    label: str = Field(min_length=1)
    condition: ExpressionNode
    then_body: list[ModuleItem] = Field(default_factory=list)
    else_body: list[ModuleItem] = Field(default_factory=list)


ModuleItem = Annotated[
    Signal
    | Variable
    | ContinuousAssignment
    | CombinationalProcess
    | SequentialProcess
    | Instance
    | ForGenerate
    | IfGenerate,
    Field(discriminator="kind"),
]


class Module(IRNode):
    """不绑定源语言 entity/module 术语差异的设计单元。"""

    kind: TypingLiteral["module"] = "module"
    name: str = Field(min_length=1)
    parameters: list[Parameter] = Field(default_factory=list)
    ports: list[Port] = Field(default_factory=list)
    signals: list[Signal] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    items: list[ModuleItem] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("module name must not be blank")
        return value

    @model_validator(mode="after")
    def validate_declaration_names(self) -> Module:
        names = [
            declaration.name
            for group in (self.parameters, self.ports, self.signals, self.variables)
            for declaration in group
        ]
        if len(names) != len(set(names)):
            raise ValueError("duplicate declaration name in module")
        return self

    @property
    def continuous_assignments(self) -> list[ContinuousAssignment]:
        return [item for item in self.items if isinstance(item, ContinuousAssignment)]

    @property
    def processes(self) -> list[CombinationalProcess | SequentialProcess]:
        return [
            item
            for item in self.items
            if isinstance(item, CombinationalProcess | SequentialProcess)
        ]

    @property
    def instances(self) -> list[Instance]:
        return [item for item in self.items if isinstance(item, Instance)]

    @property
    def generates(self) -> list[ForGenerate | IfGenerate]:
        return [item for item in self.items if isinstance(item, ForGenerate | IfGenerate)]


for _model in (ForGenerate, IfGenerate, Module):
    _model.model_rebuild(_types_namespace={"ModuleItem": ModuleItem})
