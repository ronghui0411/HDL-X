"""从 VHDL render IR 生成可读的 VHDL-2008。"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from hdl_x.ir import Comment, Design
from hdl_x.transformer.identifier_resolver import NameStyle

from .base import Generator
from .vhdl_ir import VhdlItemIR, VhdlRenderIR, VhdlStatementIR
from .vhdl_lowering import VhdlLowering


class VhdlRenderer:
    """只格式化已经完成 VHDL-specific 决策的目标 IR。"""

    def __init__(self, *, template_directory: Path | None = None) -> None:
        directory = template_directory or (
            Path(__file__).resolve().parent.parent / "templates" / "vhdl"
        )
        self._environment = Environment(
            loader=FileSystemLoader(str(directory)),
            autoescape=False,
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        self._environment.filters["vhdl_comment"] = self._render_comment
        self._environment.filters["vhdl_statement"] = self._render_statement
        self._environment.filters["vhdl_item"] = self._render_item
        self._template = self._environment.get_template("design_unit.j2")
        self._statement_template = self._environment.get_template("statement.j2")
        self._item_template = self._environment.get_template("item.j2")

    def render(self, render_ir: VhdlRenderIR) -> str:
        """渲染所有 entity/architecture，并规范化为单个结尾换行。"""

        if not isinstance(render_ir, VhdlRenderIR):
            raise TypeError("VhdlRenderer.render requires VhdlRenderIR")
        text = "\n\n".join(
            self._template.render(unit=unit).strip("\r\n")
            for unit in render_ir.units
        )
        return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"

    def _render_item(
        self,
        item: VhdlItemIR,
        level: int,
        include_comments: bool = True,
    ) -> str:
        context: dict[str, object] = {
            "item": item,
            "kind": item.kind,
            "indent": "    " * level,
            "include_comments": include_comments,
        }
        if item.kind == "process":
            context["body_text"] = self._render_children(item.body, level + 1)
        elif item.kind == "for_generate":
            context["items_text"] = "\n".join(
                self._render_item(child, level + 1) for child in item.items
            )
        elif item.kind == "if_generate":
            context["then_items_text"] = "\n".join(
                self._render_item(child, level + 1) for child in item.then_items
            )
            context["else_items_text"] = "\n".join(
                self._render_item(child, level + 1) for child in item.else_items
            )
        return self._item_template.render(**context).strip("\r\n")

    def _render_statement(self, statement: VhdlStatementIR, level: int) -> str:
        indent = "    " * level
        kind = statement.kind
        context: dict[str, object] = {"kind": kind, "indent": indent}
        if kind == "assignment":
            context.update(
                target=statement.target,
                operator=statement.operator,
                value=statement.value,
            )
        elif kind == "if":
            context.update(
                condition=statement.condition,
                then_text=self._render_children(statement.then_body, level + 1),
                else_text=(
                    self._render_children(statement.else_body, level + 1)
                    if statement.else_body
                    else ""
                ),
            )
        elif kind == "case":
            alternatives = [
                self._statement_template.render(
                    kind="case_alternative",
                    indent="    " * (level + 1),
                    selectors=" | ".join(alternative.selectors),
                    body_text=self._render_children(alternative.body, level + 2),
                ).strip("\r\n")
                for alternative in statement.alternatives
            ]
            context.update(
                expression=statement.expression,
                alternatives_text="\n".join(alternatives),
                default_text=self._render_children(statement.default_body, level + 2),
            )
        rendered = self._statement_template.render(**context).strip("\r\n")
        lines = [
            *(
                self._indented_comment(comment, indent)
                for comment in statement.leading_comments
            ),
            rendered,
            *(
                self._indented_comment(comment, indent)
                for comment in statement.trailing_comments
            ),
        ]
        return "\n".join(lines)

    def _render_children(
        self,
        statements: tuple[VhdlStatementIR, ...],
        level: int,
    ) -> str:
        if not statements:
            return self._statement_template.render(
                kind="null",
                indent="    " * level,
            ).strip("\r\n")
        return "\n".join(self._render_statement(item, level) for item in statements)

    @classmethod
    def _indented_comment(cls, comment: Comment, indent: str) -> str:
        return "\n".join(
            f"{indent}{line}" for line in cls._render_comment(comment).splitlines()
        )

    @staticmethod
    def _render_comment(comment: Comment) -> str:
        lines = comment.text.rstrip("\r\n").splitlines() or [""]
        return "\n".join(f"-- {line}" for line in lines)


class VhdlGenerator(Generator):
    """兼容 generator API；新 pipeline 主路径直接调用 lowering 和 renderer。"""

    def __init__(
        self,
        *,
        name_style: NameStyle = NameStyle.PRESERVE,
        lowering: VhdlLowering | None = None,
        renderer: VhdlRenderer | None = None,
        template_directory: Path | None = None,
    ) -> None:
        self._lowering = lowering or VhdlLowering(name_style=name_style)
        if renderer is not None and template_directory is not None:
            raise ValueError("renderer and template_directory cannot be combined")
        self._renderer = renderer or VhdlRenderer(template_directory=template_directory)

    def generate(self, design: Design) -> str:
        """兼容入口：先执行明确 VHDL lowering，再交给纯 renderer。"""

        return self._renderer.render(self._lowering.lower(design))


__all__ = ["VhdlGenerator", "VhdlRenderer"]
