"""VHDL 行注释的轻量扫描与 canonical source trivia 映射。"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from hdl_x.ir import (
    Comment,
    CommentKind,
    CommentPlacement,
    IRNode,
    SourceLocation,
    SourceSpan,
)


@dataclass(frozen=True, slots=True)
class NodeCommentAssociation:
    """一个输入节点及其按 source span 找到的注释。"""

    node_index: int
    leading_comments: tuple[Comment, ...] = ()
    trailing_comments: tuple[Comment, ...] = ()


@dataclass(frozen=True, slots=True)
class CommentAssociationResult:
    """纯关联结果；调用方可决定是否复制或更新 canonical 节点。"""

    associations: tuple[NodeCommentAssociation, ...]
    unassociated_comments: tuple[Comment, ...] = ()


class VhdlCommentScanner:
    """扫描 VHDL ``--`` 注释，不承担任何 HDL 语法解析职责。"""

    def __init__(self, *, file: str | Path | None = None) -> None:
        self.file = str(file) if file is not None else None

    def scan(self, source: str) -> list[Comment]:
        """按源码顺序返回行注释，并保留行列及字符偏移。"""

        comments: list[Comment] = []
        line_offset = 0

        for line_number, raw_line in enumerate(source.splitlines(keepends=True), start=1):
            line = self._without_line_ending(raw_line)
            marker_index = self._find_comment_marker(line)
            if marker_index is not None:
                comments.append(
                    self._make_comment(
                        line=line,
                        line_number=line_number,
                        line_offset=line_offset,
                        marker_index=marker_index,
                    )
                )
            line_offset += len(raw_line)

        return comments

    def _make_comment(
        self,
        *,
        line: str,
        line_number: int,
        line_offset: int,
        marker_index: int,
    ) -> Comment:
        raw_text = line[marker_index + 2 :]
        text, kind = self._normalize_text(raw_text)
        placement = (
            CommentPlacement.TRAILING
            if line[:marker_index].strip()
            else CommentPlacement.LEADING
        )
        span = SourceSpan(
            start=SourceLocation(
                file=self.file,
                line=line_number,
                column=marker_index + 1,
                offset=line_offset + marker_index,
            ),
            # 采用半开区间，结束位置指向注释正文后的行末位置。
            end=SourceLocation(
                file=self.file,
                line=line_number,
                column=len(line) + 1,
                offset=line_offset + len(line),
            ),
        )
        return Comment(
            text=text,
            kind=kind,
            placement=placement,
            source_span=span,
        )

    @staticmethod
    def _find_comment_marker(line: str) -> int | None:
        in_string = False
        index = 0

        while index < len(line):
            character = line[index]
            if character == '"':
                if in_string and index + 1 < len(line) and line[index + 1] == '"':
                    # VHDL 字符串以相邻双引号表示一个字面双引号。
                    index += 2
                    continue
                in_string = not in_string
                index += 1
                continue

            if (
                not in_string
                and character == "-"
                and index + 1 < len(line)
                and line[index + 1] == "-"
            ):
                return index
            index += 1

        return None

    @staticmethod
    def _normalize_text(raw_text: str) -> tuple[str, CommentKind]:
        # 去掉分隔符后的一个常规空格，同时保留额外对齐空白。
        text = raw_text[1:] if raw_text.startswith((" ", "\t")) else raw_text
        kind = CommentKind.LINE
        if text.startswith("!"):
            kind = CommentKind.DOC
            text = text[1:]
            if text.startswith((" ", "\t")):
                text = text[1:]

        # canonical Comment 要求非空；单个空格忠实表达空行注释。
        return (text or " "), kind

    @staticmethod
    def _without_line_ending(raw_line: str) -> str:
        if raw_line.endswith("\n"):
            raw_line = raw_line[:-1]
        if raw_line.endswith("\r"):
            raw_line = raw_line[:-1]
        return raw_line


def scan_vhdl_comments(
    source: str,
    *,
    file: str | Path | None = None,
) -> list[Comment]:
    """使用轻量扫描器从 VHDL 源文本提取 canonical 注释。"""

    return VhdlCommentScanner(file=file).scan(source)


def associate_comments_by_source_span(
    comments: Sequence[Comment],
    nodes: Sequence[IRNode],
    *,
    source: str | None = None,
) -> CommentAssociationResult:
    """按最近 source span 关联注释，不修改注释或 canonical 节点。

    提供 ``source`` 时，leading 注释与目标节点之间只能出现空白或其他
    独立注释行。这样 context clause、architecture header 等真实 HDL 文本
    不会被轻率跨越。
    """

    leading: list[list[Comment]] = [[] for _ in nodes]
    trailing: list[list[Comment]] = [[] for _ in nodes]
    unassociated: list[Comment] = []
    source_lines = None if source is None else tuple(source.splitlines())

    for comment in comments:
        if comment.source_span is None:
            unassociated.append(comment)
            continue

        node_index = _nearest_node_index(comment, nodes, source_lines=source_lines)
        if node_index is None:
            unassociated.append(comment)
        elif comment.placement is CommentPlacement.TRAILING:
            trailing[node_index].append(comment)
        else:
            leading[node_index].append(comment)

    associations = tuple(
        NodeCommentAssociation(
            node_index=index,
            leading_comments=tuple(leading[index]),
            trailing_comments=tuple(trailing[index]),
        )
        for index in range(len(nodes))
    )
    return CommentAssociationResult(
        associations=associations,
        unassociated_comments=tuple(unassociated),
    )


def _nearest_node_index(
    comment: Comment,
    nodes: Sequence[IRNode],
    *,
    source_lines: Sequence[str] | None = None,
) -> int | None:
    assert comment.source_span is not None
    comment_span = comment.source_span

    if comment.placement is CommentPlacement.TRAILING:
        candidates = [
            (index, node.source_span)
            for index, node in enumerate(nodes)
            if node.source_span is not None
            and _same_source_file(comment_span, node.source_span)
            and node.source_span.end.line == comment_span.start.line
            and node.source_span.end.column <= comment_span.start.column
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda item: (
                item[1].end.column,
                item[1].start.column,
                -item[0],
            ),
        )[0]

    candidates = [
        (index, node.source_span)
        for index, node in enumerate(nodes)
        if node.source_span is not None
        and _same_source_file(comment_span, node.source_span)
        and (node.source_span.start.line, node.source_span.start.column)
        >= (comment_span.end.line, comment_span.end.column)
        and _leading_gap_contains_only_trivia(
            comment_span,
            node.source_span,
            source_lines,
        )
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            item[1].start.line,
            item[1].start.column,
            item[0],
        ),
    )[0]


def _leading_gap_contains_only_trivia(
    comment_span: SourceSpan,
    node_span: SourceSpan,
    source_lines: Sequence[str] | None,
) -> bool:
    """拒绝跨越真实 HDL token 的 leading 关联。"""

    if source_lines is None:
        return True
    if node_span.start.line <= comment_span.end.line:
        return True

    first_line = comment_span.end.line + 1
    last_line = node_span.start.line - 1
    if first_line > last_line:
        return True
    if first_line < 1 or last_line > len(source_lines):
        return False

    for line_number in range(first_line, last_line + 1):
        stripped = source_lines[line_number - 1].strip()
        if stripped and not stripped.startswith("--"):
            return False
    return True


def _same_source_file(left: SourceSpan, right: SourceSpan) -> bool:
    left_file = left.file
    right_file = right.file
    if left_file is None or right_file is None:
        return True
    return os.path.normcase(os.path.abspath(left_file)) == os.path.normcase(
        os.path.abspath(right_file)
    )
