"""Canonical RTL 语句与进程语义。"""

from __future__ import annotations

from enum import Enum
from typing import Annotated
from typing import Literal as TypingLiteral

from pydantic import Field, model_validator

from .base import ActiveLevel, EdgeKind, IRNode, ResetKind
from .expressions import ExpressionNode
from .types import VectorRange


class AssignmentKind(str, Enum):
    """v0.1 兼容的目标赋值操作符提示；计划在 v0.2 后由 target IR 取代。"""

    BLOCKING = "blocking"
    NON_BLOCKING = "non_blocking"


class Statement(IRNode):
    """过程语句的共同基类。"""


class ContinuousAssignment(Statement):
    """并发驱动关系。"""

    kind: TypingLiteral["continuous_assignment"] = "continuous_assignment"
    target: ExpressionNode
    value: ExpressionNode


class ProceduralAssignment(Statement):
    """v0.1 兼容过程赋值节点；公开 JSON 结构在本版本保持不变。"""

    kind: TypingLiteral["procedural_assignment"] = "procedural_assignment"
    target: ExpressionNode
    value: ExpressionNode
    assignment_kind: AssignmentKind = Field(
        json_schema_extra={"deprecated": True},
    )


class IfStatement(Statement):
    """条件过程语句，else-if 使用嵌套节点表示。"""

    kind: TypingLiteral["if_statement"] = "if_statement"
    condition: ExpressionNode
    then_body: list[StatementNode] = Field(default_factory=list)
    else_body: list[StatementNode] = Field(default_factory=list)


class CaseAlternative(IRNode):
    """一组具有相同语句体的 case 选择值。"""

    selectors: list[ExpressionNode] = Field(min_length=1)
    body: list[StatementNode] = Field(default_factory=list)


class CaseStatement(Statement):
    """精确匹配的多路选择语句。"""

    kind: TypingLiteral["case_statement"] = "case_statement"
    expression: ExpressionNode
    alternatives: list[CaseAlternative] = Field(default_factory=list)
    default_body: list[StatementNode] = Field(default_factory=list)


class ForStatement(Statement):
    """具有离散范围的可综合循环。"""

    kind: TypingLiteral["for_statement"] = "for_statement"
    index_name: str = Field(min_length=1)
    range: VectorRange
    body: list[StatementNode] = Field(default_factory=list)


class BlockStatement(Statement):
    """保持语句分组和可选层次标签。"""

    kind: TypingLiteral["block_statement"] = "block_statement"
    label: str | None = None
    statements: list[StatementNode] = Field(default_factory=list)


class NullStatement(Statement):
    """显式空操作。"""

    kind: TypingLiteral["null_statement"] = "null_statement"


StatementNode = Annotated[
    ContinuousAssignment
    | ProceduralAssignment
    | IfStatement
    | CaseStatement
    | ForStatement
    | BlockStatement
    | NullStatement,
    Field(discriminator="kind"),
]


class ResetSpec(IRNode):
    """不依赖 VHDL/Verilog 拼写的复位语义。"""

    signal: ExpressionNode
    kind: ResetKind
    active_level: ActiveLevel


class CombinationalProcess(IRNode):
    """组合过程；空 sensitivity 表示由 generator 使用完整隐式敏感集。"""

    kind: TypingLiteral["combinational_process"] = "combinational_process"
    label: str | None = None
    sensitivity: list[ExpressionNode] = Field(default_factory=list)
    body: list[StatementNode] = Field(default_factory=list)


class SequentialProcess(IRNode):
    """单时钟时序过程及其可选同步/异步复位分支。"""

    kind: TypingLiteral["sequential_process"] = "sequential_process"
    label: str | None = None
    clock: ExpressionNode
    edge: EdgeKind
    reset: ResetSpec | None = None
    reset_body: list[StatementNode] = Field(default_factory=list)
    body: list[StatementNode] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_reset_body(self) -> SequentialProcess:
        if self.reset is None and self.reset_body:
            raise ValueError("reset_body requires reset semantics")
        return self


ProcessNode = Annotated[
    CombinationalProcess | SequentialProcess,
    Field(discriminator="kind"),
]


for _model in (
    IfStatement,
    CaseAlternative,
    CaseStatement,
    ForStatement,
    BlockStatement,
    CombinationalProcess,
    SequentialProcess,
):
    _model.model_rebuild(_types_namespace={"StatementNode": StatementNode})
