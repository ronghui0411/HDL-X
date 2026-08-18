"""GHDL frontend 与 canonical IR 之间的私有 VHDL 表示。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class RawSourceLocation:
    """frontend 私有节点的 1-based 起始位置及可选结束位置。"""

    file: Path
    line: int
    column: int
    end_line: int | None = None
    end_column: int | None = None


class RawRangeDirection(str, Enum):
    """VHDL 离散范围方向。"""

    TO = "to"
    DOWNTO = "downto"


class RawPortDirection(str, Enum):
    """VHDL 接口对象方向。"""

    IN = "in"
    OUT = "out"
    INOUT = "inout"


class RawInstantiationKind(str, Enum):
    """VHDL 实例引用采用的语言构造。"""

    DIRECT_ENTITY = "direct_entity"
    COMPONENT = "component"


class RawTypeKind(str, Enum):
    """当前 frontend 安全识别的 RTL 类型类别。"""

    SCALAR = "scalar"
    VECTOR = "vector"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class RawLiteralKind(str, Enum):
    """不依赖 pyGHDL 类的字面量类别。"""

    INTEGER = "integer"
    BOOLEAN = "boolean"
    BIT = "bit"
    BIT_VECTOR = "bit_vector"
    STRING = "string"


class RawUnaryOperator(str, Enum):
    """VHDL 一元运算。"""

    NOT = "not"
    NEGATE = "negate"
    POSITIVE = "positive"


class RawBinaryOperator(str, Enum):
    """已由 GHDL 结构化解析的 VHDL 二元运算。"""

    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"
    MODULO = "modulo"
    POWER = "power"
    AND = "and"
    NAND = "nand"
    OR = "or"
    NOR = "nor"
    XOR = "xor"
    XNOR = "xnor"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    LESS_THAN = "less_than"
    LESS_EQUAL = "less_equal"
    GREATER_THAN = "greater_than"
    GREATER_EQUAL = "greater_equal"
    CONCATENATE = "concatenate"


class RawEdgeKind(str, Enum):
    """时钟有效边沿。"""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class RawResetKind(str, Enum):
    """复位相对时钟的时序关系。"""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class RawActiveLevel(str, Enum):
    """复位控制信号的有效电平。"""

    HIGH = "high"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class RawIdentifier:
    """VHDL 名称引用。"""

    name: str
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawLiteral:
    """VHDL 字面量。"""

    value: bool | int | str
    kind: RawLiteralKind
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawUnaryExpression:
    """一元表达式。"""

    operator: RawUnaryOperator
    operand: RawExpression
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawBinaryExpression:
    """二元表达式。"""

    left: RawExpression
    operator: RawBinaryOperator
    right: RawExpression
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawIndexExpression:
    """单一索引名称。"""

    value: RawExpression
    index: RawExpression
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawConditionalExpression:
    """按条件选择两个值的表达式。"""

    condition: RawExpression
    when_true: RawExpression
    when_false: RawExpression
    source: RawSourceLocation | None = None


RawExpression: TypeAlias = (
    RawIdentifier
    | RawLiteral
    | RawUnaryExpression
    | RawBinaryExpression
    | RawIndexExpression
    | RawConditionalExpression
)


@dataclass(frozen=True, slots=True)
class RawRange:
    """保留 VHDL 左右边界与索引方向。"""

    left: RawExpression
    right: RawExpression
    direction: RawRangeDirection
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawType:
    """VHDL 类型在 frontend 边界上的语义摘要。"""

    kind: RawTypeKind
    source_name: str
    signed: bool = False
    four_state: bool = False
    range: RawRange | None = None
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawParameter:
    """VHDL generic 声明。"""

    name: str
    type: RawType
    default: RawExpression | None = None
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawPort:
    """VHDL entity 端口。"""

    name: str
    direction: RawPortDirection
    type: RawType
    source: RawSourceLocation | None = None
    default: RawExpression | None = None


@dataclass(frozen=True, slots=True)
class RawSignal:
    """VHDL architecture 声明区中的 signal。"""

    name: str
    type: RawType
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawEntity:
    """与 pyGHDL 对象完全解耦的 entity 摘要。"""

    name: str
    parameters: tuple[RawParameter, ...] = ()
    ports: tuple[RawPort, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawComponentDeclaration:
    """component 声明的完整接口；仅用于证明默认绑定语义。"""

    name: str
    parameters: tuple[RawParameter, ...] = ()
    ports: tuple[RawPort, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawConcurrentAssignment:
    """无延时、单波形的并发信号赋值。"""

    target: RawExpression
    value: RawExpression
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawProceduralAssignment:
    """process 内的 VHDL 信号赋值。"""

    target: RawExpression
    value: RawExpression
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawIfStatement:
    """elsif 已规范化为 else_body 中的嵌套 if。"""

    condition: RawExpression
    then_body: tuple[RawStatement, ...] = ()
    else_body: tuple[RawStatement, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawCaseAlternative:
    """共享一个语句体的 case 选择值。"""

    selectors: tuple[RawExpression, ...]
    body: tuple[RawStatement, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawCaseStatement:
    """具有可选 others 分支的 case 语句。"""

    expression: RawExpression
    alternatives: tuple[RawCaseAlternative, ...] = ()
    default_body: tuple[RawStatement, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawNullStatement:
    """显式 null 语句。"""

    source: RawSourceLocation | None = None


RawStatement: TypeAlias = (
    RawProceduralAssignment | RawIfStatement | RawCaseStatement | RawNullStatement
)


@dataclass(frozen=True, slots=True)
class RawCombinationalProcess:
    """具有显式敏感列表的组合 process。"""

    label: str | None
    sensitivity: tuple[RawExpression, ...]
    body: tuple[RawStatement, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawResetSpec:
    """与源语言拼写解耦的复位语义。"""

    signal: RawIdentifier
    kind: RawResetKind
    active_level: RawActiveLevel
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawSequentialProcess:
    """单时钟 process 的结构化边沿与复位摘要。"""

    label: str | None
    sensitivity: tuple[RawIdentifier, ...]
    clock: RawIdentifier
    edge: RawEdgeKind
    reset: RawResetSpec | None = None
    reset_body: tuple[RawStatement, ...] = ()
    body: tuple[RawStatement, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawAssociation:
    """实例 generic/port map 中的命名或位置关联。"""

    formal: str | None
    position: int | None
    value: RawExpression | None
    source: RawSourceLocation | None = None

    def __post_init__(self) -> None:
        if (self.formal is None) == (self.position is None):
            raise ValueError("raw association requires exactly one selector")
        if self.position is not None and self.position < 0:
            raise ValueError("raw association position must not be negative")


@dataclass(frozen=True, slots=True)
class RawInstance:
    """保持实例 label、引用单元及关联表的层次节点。"""

    referenced_unit: str
    name: str
    parameter_associations: tuple[RawAssociation, ...] = ()
    port_associations: tuple[RawAssociation, ...] = ()
    source: RawSourceLocation | None = None
    instantiation_kind: RawInstantiationKind = RawInstantiationKind.DIRECT_ENTITY
    component_declaration: RawComponentDeclaration | None = None


@dataclass(frozen=True, slots=True)
class RawForGenerate:
    """保留范围、label 与局部层次的 VHDL for-generate。"""

    label: str
    index_name: str
    range: RawRange
    body: tuple[RawArchitectureItem, ...] = ()
    source: RawSourceLocation | None = None


@dataclass(frozen=True, slots=True)
class RawIfGenerate:
    """保留互斥分支与局部层次的 VHDL if-generate。"""

    label: str
    condition: RawExpression
    then_body: tuple[RawArchitectureItem, ...] = ()
    else_body: tuple[RawArchitectureItem, ...] = ()
    source: RawSourceLocation | None = None


RawArchitectureItem: TypeAlias = (
    RawSignal
    | RawConcurrentAssignment
    | RawCombinationalProcess
    | RawSequentialProcess
    | RawInstance
    | RawForGenerate
    | RawIfGenerate
)


@dataclass(frozen=True, slots=True)
class RawArchitecture:
    """VHDL architecture 及其受支持并发项。"""

    name: str
    entity_name: str
    items: tuple[RawArchitectureItem, ...] = ()
    source: RawSourceLocation | None = None
    signals: tuple[RawSignal, ...] = ()
    components: tuple[RawComponentDeclaration, ...] = ()


@dataclass(frozen=True, slots=True)
class RawDesign:
    """单次 GHDL 分析产生的私有 Raw IR。"""

    source_path: Path
    entities: tuple[RawEntity, ...] = field(default_factory=tuple)
    architectures: tuple[RawArchitecture, ...] = field(default_factory=tuple)


__all__ = [
    "RawActiveLevel",
    "RawAssociation",
    "RawArchitecture",
    "RawArchitectureItem",
    "RawBinaryExpression",
    "RawBinaryOperator",
    "RawCaseAlternative",
    "RawCaseStatement",
    "RawCombinationalProcess",
    "RawComponentDeclaration",
    "RawConcurrentAssignment",
    "RawConditionalExpression",
    "RawDesign",
    "RawEdgeKind",
    "RawEntity",
    "RawExpression",
    "RawForGenerate",
    "RawIdentifier",
    "RawIfStatement",
    "RawIfGenerate",
    "RawIndexExpression",
    "RawInstantiationKind",
    "RawInstance",
    "RawLiteral",
    "RawLiteralKind",
    "RawNullStatement",
    "RawParameter",
    "RawPort",
    "RawPortDirection",
    "RawProceduralAssignment",
    "RawRange",
    "RawRangeDirection",
    "RawResetKind",
    "RawResetSpec",
    "RawSequentialProcess",
    "RawSignal",
    "RawSourceLocation",
    "RawStatement",
    "RawType",
    "RawTypeKind",
    "RawUnaryExpression",
    "RawUnaryOperator",
]
