"""Canonical IR 的基础模型与源代码溯源信息。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HDLXModel(BaseModel):
    """HDL-X 中需要严格校验的数据模型基类。"""

    model_config = ConfigDict(extra="forbid", strict=True, validate_assignment=True)


class SourceLocation(HDLXModel):
    """源文件中的一个位置，行列号均从 1 开始。"""

    file: str | None = None
    line: int = Field(ge=1)
    column: int = Field(ge=1)
    offset: int | None = Field(default=None, ge=0)


class SourceSpan(HDLXModel):
    """半开或闭合区间语义由 frontend 保留，此处只记录有序端点。"""

    start: SourceLocation
    end: SourceLocation

    @model_validator(mode="after")
    def validate_order(self) -> SourceSpan:
        """拒绝跨文件或反向的源区间。"""

        if (
            self.start.file is not None
            and self.end.file is not None
            and self.start.file != self.end.file
        ):
            raise ValueError("source span endpoints must belong to the same file")

        if (self.end.line, self.end.column) < (self.start.line, self.start.column):
            raise ValueError("source span end precedes start")
        if (
            self.start.offset is not None
            and self.end.offset is not None
            and self.end.offset < self.start.offset
        ):
            raise ValueError("source span end precedes start")
        return self

    @property
    def file(self) -> str | None:
        """返回区间关联的源文件。"""

        return self.start.file or self.end.file


class CommentKind(str, Enum):
    """与具体 HDL 注释标记无关的注释种类。"""

    LINE = "line"
    BLOCK = "block"
    DOC = "doc"


class CommentPlacement(str, Enum):
    """注释相对所附 IR 节点的位置。"""

    LEADING = "leading"
    TRAILING = "trailing"


class Comment(HDLXModel):
    """从源码 trivia 映射而来的注释。"""

    text: str = Field(min_length=1)
    kind: CommentKind = CommentKind.LINE
    placement: CommentPlacement = CommentPlacement.LEADING
    source_span: SourceSpan | None = None


class RangeDirection(str, Enum):
    """范围索引递增或递减的语义方向。"""

    ASCENDING = "ascending"
    DESCENDING = "descending"


class EdgeKind(str, Enum):
    """时钟有效边沿。"""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class ResetKind(str, Enum):
    """复位相对时钟的时序关系。"""

    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class ActiveLevel(str, Enum):
    """控制信号的有效电平。"""

    HIGH = "high"
    LOW = "low"


class IRNode(HDLXModel):
    """所有 canonical RTL IR 节点的共同基类。"""

    source_span: SourceSpan | None = None
    leading_comments: list[Comment] = Field(default_factory=list)
    trailing_comments: list[Comment] = Field(default_factory=list)
