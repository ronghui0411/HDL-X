"""完成 VHDL-specific lowering 后交给 renderer 的目标 IR。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from hdl_x.ir import Comment, Design


@dataclass(frozen=True, slots=True)
class VhdlDeclarationIR:
    """已经确定目标名称、类型、方向和默认值的声明。"""

    name: str
    type_text: str
    mode: str | None = None
    default_text: str | None = None
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlConcurrentAssignmentIR:
    """已经完成表达式 lowering 的并发 signal assignment。"""

    kind: str = field(init=False, default="concurrent_assignment")
    target: str
    value: str
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlAssignmentIR:
    """过程内已决定 signal/variable operator 的赋值。"""

    kind: str = field(init=False, default="assignment")
    target: str
    operator: str
    value: str
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlIfStatementIR:
    """VHDL boolean condition 与完整分支。"""

    kind: str = field(init=False, default="if")
    condition: str
    then_body: tuple[VhdlStatementIR, ...]
    else_body: tuple[VhdlStatementIR, ...] = ()
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlCaseAlternativeIR:
    """一个或多个选择值共享的 case 分支。"""

    selectors: tuple[str, ...]
    body: tuple[VhdlStatementIR, ...]


@dataclass(frozen=True, slots=True)
class VhdlCaseStatementIR:
    """已完成 selector 类型与 literal lowering 的 case。"""

    kind: str = field(init=False, default="case")
    expression: str
    alternatives: tuple[VhdlCaseAlternativeIR, ...]
    default_body: tuple[VhdlStatementIR, ...] = ()
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlNullStatementIR:
    """显式 null statement。"""

    kind: str = field(init=False, default="null")
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


VhdlStatementIR = (
    VhdlAssignmentIR
    | VhdlIfStatementIR
    | VhdlCaseStatementIR
    | VhdlNullStatementIR
)


@dataclass(frozen=True, slots=True)
class VhdlProcessIR:
    """已完成敏感集、局部变量和时序骨架决策的 process。"""

    kind: str = field(init=False, default="process")
    label: str
    sensitivity: tuple[str, ...]
    declarations: tuple[VhdlDeclarationIR, ...]
    body: tuple[VhdlStatementIR, ...]
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlAssociationIR:
    """generic/port map 中的命名或位置关联。"""

    formal: str | None
    value: str


@dataclass(frozen=True, slots=True)
class VhdlInstanceIR:
    """已决定 entity 名称和 association style 的实例。"""

    kind: str = field(init=False, default="instance")
    label: str
    entity_name: str
    generic_map: tuple[VhdlAssociationIR, ...] = ()
    port_map: tuple[VhdlAssociationIR, ...] = ()
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlForGenerateIR:
    """已完成离散范围、局部声明和层次名称决策的 for-generate。"""

    kind: str = field(init=False, default="for_generate")
    label: str
    index_name: str
    left: str
    direction: str
    right: str
    declarations: tuple[VhdlDeclarationIR, ...]
    items: tuple[VhdlItemIR, ...]
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlIfGenerateIR:
    """已完成静态条件与分支局部作用域决策的 if-generate。"""

    kind: str = field(init=False, default="if_generate")
    label: str
    condition: str
    then_declarations: tuple[VhdlDeclarationIR, ...]
    then_items: tuple[VhdlItemIR, ...]
    else_declarations: tuple[VhdlDeclarationIR, ...] = ()
    else_items: tuple[VhdlItemIR, ...] = ()
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


VhdlItemIR = (
    VhdlConcurrentAssignmentIR
    | VhdlProcessIR
    | VhdlInstanceIR
    | VhdlForGenerateIR
    | VhdlIfGenerateIR
)


@dataclass(frozen=True, slots=True)
class VhdlDesignUnitIR:
    """一对 entity/architecture 的完整渲染输入。"""

    entity_name: str
    architecture_name: str
    generics: tuple[VhdlDeclarationIR, ...]
    ports: tuple[VhdlDeclarationIR, ...]
    signals: tuple[VhdlDeclarationIR, ...]
    items: tuple[VhdlItemIR, ...]
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class VhdlRenderIR:
    """封装已完成名称、类型、进程和目标表达式决策的 VHDL 结构。"""

    design: Design
    units: tuple[VhdlDesignUnitIR, ...]
    name_mappings: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.design, Design):
            raise TypeError("VhdlRenderIR.design must be a canonical Design")
        object.__setattr__(self, "name_mappings", MappingProxyType(dict(self.name_mappings)))


__all__ = [
    "VhdlAssignmentIR",
    "VhdlAssociationIR",
    "VhdlCaseAlternativeIR",
    "VhdlCaseStatementIR",
    "VhdlConcurrentAssignmentIR",
    "VhdlDeclarationIR",
    "VhdlDesignUnitIR",
    "VhdlForGenerateIR",
    "VhdlIfGenerateIR",
    "VhdlIfStatementIR",
    "VhdlInstanceIR",
    "VhdlItemIR",
    "VhdlNullStatementIR",
    "VhdlProcessIR",
    "VhdlRenderIR",
    "VhdlStatementIR",
]
