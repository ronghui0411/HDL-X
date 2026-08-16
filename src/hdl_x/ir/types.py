"""Canonical RTL 类型与范围语义。"""

from __future__ import annotations

from typing import Annotated
from typing import Literal as TypingLiteral

from pydantic import Field, model_validator

from .base import IRNode, RangeDirection
from .expressions import ExpressionNode, Literal

RangeBound = int | ExpressionNode


def _constant_integer(bound: RangeBound) -> int | None:
    if isinstance(bound, bool):
        return None
    if isinstance(bound, int):
        return bound
    if isinstance(bound, Literal) and isinstance(bound.value, int) and not isinstance(
        bound.value, bool
    ):
        return bound.value
    return None


class VectorRange(IRNode):
    """保留左右边界与方向的向量或离散范围。"""

    left: RangeBound
    right: RangeBound
    direction: RangeDirection

    @property
    def width(self) -> int | None:
        """常量边界可求值时返回宽度，符号边界返回 ``None``。"""

        left = _constant_integer(self.left)
        right = _constant_integer(self.right)
        if left is None or right is None:
            return None
        if self.direction is RangeDirection.ASCENDING:
            return max(right - left + 1, 0)
        return max(left - right + 1, 0)


class RTLType(IRNode):
    """所有 canonical RTL 类型的共同基类。"""


class ScalarType(RTLType):
    """单比特标量。"""

    kind: TypingLiteral["scalar"] = "scalar"
    signed: bool = False
    four_state: bool = True

    @property
    def width(self) -> int:
        return 1


class VectorType(RTLType):
    """具有显式索引范围的位向量。"""

    kind: TypingLiteral["vector"] = "vector"
    range: VectorRange
    signed: bool = False
    four_state: bool = True

    @property
    def width(self) -> int | None:
        return self.range.width


class IntegerType(RTLType):
    """可选受限范围的数学整数类型。"""

    kind: TypingLiteral["integer"] = "integer"
    minimum: int | None = None
    maximum: int | None = None
    signed: bool = True
    four_state: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> IntegerType:
        if (
            self.minimum is not None
            and self.maximum is not None
            and self.minimum > self.maximum
        ):
            raise ValueError("integer minimum must not exceed maximum")
        return self


class BooleanType(RTLType):
    """二值布尔类型。"""

    kind: TypingLiteral["boolean"] = "boolean"
    signed: bool = False
    four_state: bool = False

    @property
    def width(self) -> int:
        return 1


RTLTypeNode = Annotated[
    ScalarType | VectorType | IntegerType | BooleanType,
    Field(discriminator="kind"),
]
