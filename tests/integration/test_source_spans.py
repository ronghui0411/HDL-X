"""真实 GHDL start/end span 与多行 trailing comment 回归。"""

from pathlib import Path

import pytest

from hdl_x.frontend import VhdlFrontend
from hdl_x.ir import CombinationalProcess, ContinuousAssignment, IfGenerate
from hdl_x.parser.ghdl import PyGhdlBackend
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration

FIXTURE = Path(__file__).parents[1] / "fixtures" / "vhdl" / "v01_multiline_comments.vhd"


def test_pyghdl_raw_locations_are_one_based_and_include_real_end_lines() -> None:
    raw = PyGhdlBackend().parse(FIXTURE)

    assert raw.entities[0].source is not None
    assert raw.entities[0].source.column == 8
    signal = raw.architectures[0].signals[0]
    assert signal.source is not None
    assert signal.source.column == 10
    assert signal.source.end_line == 17
    assignment, process, generate = raw.architectures[0].items
    assert assignment.source is not None
    assert assignment.source.column == 3
    assert assignment.source.end_line == 21
    assert process.source is not None
    assert process.source.column == 3
    assert process.source.end_line == 31
    assert generate.source is not None
    assert generate.source.column == 3
    assert generate.source.end_line == 38


def test_multiline_nodes_attach_same_line_trailing_comments() -> None:
    frontend = VhdlFrontend()
    design = frontend.parse_design(FIXTURE)
    signal = design.modules[0].signals[0]
    assignment, process, generate = design.modules[0].items

    assert isinstance(assignment, ContinuousAssignment)
    assert isinstance(process, CombinationalProcess)
    assert isinstance(generate, IfGenerate)
    assert assignment.source_span is not None
    assert assignment.source_span.start.column == 3
    assert assignment.source_span.end.line == 21
    assert assignment.source_span.start.offset is None
    assert assignment.source_span.end.offset is None
    serialized_span = assignment.source_span.model_dump(mode="json")
    assert serialized_span["start"]["column"] == 3
    assert serialized_span["end"]["line"] == 21
    assert process.source_span is not None
    assert process.source_span.end.line == 31
    assert generate.source_span is not None
    assert generate.source_span.end.line == 38
    assert [item.text for item in signal.trailing_comments] == ["declaration tail"]
    assert [item.text for item in assignment.trailing_comments] == ["assignment tail"]
    assert [item.text for item in process.trailing_comments] == ["process tail"]
    assert [item.text for item in generate.trailing_comments] == ["generate tail"]
    assert frontend.unassociated_comments == ()


def test_multiline_comment_conversion_remains_strict_and_readable() -> None:
    result = convert_file(FIXTURE, options=ConversionOptions(strict=True))

    assert result.diagnostics == ()
    assert result.text.count("// declaration tail") == 1
    assert result.text.count("// assignment tail") == 1
    assert result.text.count("// process tail") == 1
    assert result.text.count("// generate tail") == 1


def test_normal_dom_process_end_span_attaches_trailing_comment(tmp_path: Path) -> None:
    source = tmp_path / "normal_multiline_process.vhd"
    source.write_text(
        """entity NormalMultilineProcess is
  port (a : in bit; y : out bit);
end entity;

architecture rtl of NormalMultilineProcess is
begin
  comb_p : process (
    a
  )
  begin
    y <= a;
  end process; -- normal process tail
end architecture;
""",
        encoding="utf-8",
    )

    frontend = VhdlFrontend()
    design = frontend.parse_design(source)
    process = design.modules[0].items[0]

    assert isinstance(process, CombinationalProcess)
    assert process.source_span is not None
    assert process.source_span.start.column == 3
    assert process.source_span.end.line == 12
    assert [item.text for item in process.trailing_comments] == ["normal process tail"]
    assert frontend.unassociated_comments == ()
