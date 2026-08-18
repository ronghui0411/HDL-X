"""真实 GHDL frontend 的静默降级防护回归。"""

from pathlib import Path

import pytest

from hdl_x.diagnostics import FrontendError, SemanticError, UnsupportedConstructError
from hdl_x.frontend import VhdlFrontend
from hdl_x.parser.ghdl import RawDesign, RawEntity
from hdl_x.parser.vhdl_adapter import VhdlAdapter
from hdl_x.pipeline import ConversionOptions, convert_file

pytestmark = pytest.mark.ghdl_integration


def test_unsupported_package_design_unit_is_not_silently_dropped(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package_constant.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
package LocalDefs is
    constant WIDTH : positive := 4;
end package;
library ieee;
use ieee.std_logic_1164.all;
use work.LocalDefs.all;
entity PackageUser is
    port (a : in std_logic_vector(WIDTH - 1 downto 0));
end entity;
architecture rtl of PackageUser is begin end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(UnsupportedConstructError) as raised:
        VhdlFrontend().parse_design(source)

    assert raised.value.code == "HDLX-VHDL-DESIGN-UNIT"


def test_entity_without_architecture_requires_explicit_future_blackbox_policy() -> None:
    raw = RawDesign(Path("entity_only.vhd"), entities=(RawEntity("Leaf"),))

    with pytest.raises(SemanticError) as raised:
        VhdlAdapter().adapt(raw)

    assert raised.value.code == "HDLX-VHDL-ARCHITECTURE-MISSING"


def test_integer_port_is_rejected_before_invalid_verilog_is_generated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "integer_port.vhd"
    source.write_text(
        """entity IntegerPort is
    port (a : in integer; y : out bit);
end entity;
architecture rtl of IntegerPort is
begin
    y <= '1' when a = 1 else '0';
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-PORT-TYPE"
    assert raised.value.diagnostic.file == str(source.resolve())
    assert raised.value.diagnostic.line == 2


def test_normal_dom_path_still_runs_real_ghdl_semantics(tmp_path: Path) -> None:
    source = tmp_path / "unresolved_name.vhd"
    source.write_text(
        """entity UnresolvedName is
    port (a : in bit; y : out bit);
end entity;
architecture rtl of UnresolvedName is
begin
    y <= a and missing_name;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(FrontendError) as raised:
        VhdlFrontend().parse_design(source)

    assert raised.value.code == "HDLX-GHDL-ANALYZE"
    assert raised.value.diagnostic.file == str(source.resolve())
    assert raised.value.diagnostic.line == 6
    assert raised.value.diagnostic.column == 16


def test_type_conversion_is_not_misclassified_as_array_index(tmp_path: Path) -> None:
    source = tmp_path / "unsupported_cast.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity UnsupportedCast is
    port (
        a : in std_logic_vector(3 downto 0);
        y : out unsigned(3 downto 0)
    );
end entity;
architecture rtl of UnsupportedCast is
begin
    y <= unsigned(a);
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        VhdlFrontend().parse_design(source)

    assert raised.value.code == "HDLX-VHDL-INDEX-BASE"


def test_signed_vector_comparison_contextualizes_bit_string_literal() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "vhdl" / "m8_signed_compare.vhd"

    result = convert_file(fixture, options=ConversionOptions(strict=True))

    assert "input wire signed [3:0] a" in result.text
    assert "a < 4'sb0001 === 1'b1" in result.text or (
        "(a < 4'sb0001) === 1'b1" in result.text
    )


def test_signedness_propagates_through_nested_vector_arithmetic(
    tmp_path: Path,
) -> None:
    source = tmp_path / "nested_signed_arithmetic.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity NestedSignedArithmetic is
    port (a : in signed(3 downto 0); y : out std_logic);
end entity;
architecture rtl of NestedSignedArithmetic is
begin
    y <= '1' when a + "0000" < "0001" else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "a + 4'sb0000 < 4'sb0001 === 1'b1" in result.text or (
        "(a + 4'sb0000 < 4'sb0001) === 1'b1" in result.text
    )


def test_unary_signed_bit_vector_literal_keeps_signed_comparison(
    tmp_path: Path,
) -> None:
    source = tmp_path / "unary_signed_literal.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity UnarySignedLiteral is
    port (y : out std_logic);
end entity;
architecture rtl of UnarySignedLiteral is
begin
    y <= '1' when -"0001" < "0000" else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "-4'sb0001 < 4'sb0000 === 1'b1" in result.text or (
        "(-4'sb0001 < 4'sb0000) === 1'b1" in result.text
    )


def test_std_logic_equality_uses_exact_four_state_comparison(
    tmp_path: Path,
) -> None:
    source = tmp_path / "four_state_equal.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity FourStateEqual is
    port (a : in std_logic; y : out std_logic);
end entity;
architecture rtl of FourStateEqual is
begin
    y <= '1' when a = 'X' else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "a === 1'bx ? 1'b1 : 1'b0" in result.text


def test_numeric_std_equality_normalizes_meta_values_to_boolean(
    tmp_path: Path,
) -> None:
    source = tmp_path / "numeric_equality.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity NumericEquality is
    port (
        a : in signed(3 downto 0);
        b : in signed(3 downto 0);
        equal_y : out std_logic;
        unequal_y : out std_logic
    );
end entity;
architecture rtl of NumericEquality is
begin
    equal_y <= '1' when a = b else '0';
    unequal_y <= '1' when a /= b else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "a == b === 1'b1 ? 1'b1 : 1'b0" in result.text or (
        "(a == b) === 1'b1 ? 1'b1 : 1'b0" in result.text
    )
    assert "a != b !== 1'b0 ? 1'b1 : 1'b0" in result.text or (
        "(a != b) !== 1'b0 ? 1'b1 : 1'b0" in result.text
    )


def test_std_logic_relational_ordering_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "logic_relational.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity LogicRelational is
    port (a : in std_logic; b : in std_logic; y : out std_logic);
end entity;
architecture rtl of LogicRelational is
begin
    y <= '1' when a < b else '0';
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-FOUR-STATE-RELATIONAL"


def test_predefined_vector_equality_requires_proven_equal_width(
    tmp_path: Path,
) -> None:
    source = tmp_path / "vector_equality_width.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity VectorEqualityWidth is
    port (
        a : in std_logic_vector(3 downto 0);
        b : in std_logic_vector(7 downto 0);
        y : out std_logic
    );
end entity;
architecture rtl of VectorEqualityWidth is
begin
    y <= '1' when a = b else '0';
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-VECTOR-COMPARISON-WIDTH"


def test_predefined_vector_equality_accepts_proven_equal_width(
    tmp_path: Path,
) -> None:
    source = tmp_path / "vector_equality_equal_width.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity VectorEqualityEqualWidth is
    port (
        a : in std_logic_vector(3 downto 0);
        b : in std_logic_vector(0 to 3);
        y : out std_logic
    );
end entity;
architecture rtl of VectorEqualityEqualWidth is
begin
    y <= '1' when a = b else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "a === b ? 1'b1 : 1'b0" in result.text


def test_static_null_vector_range_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "null_vector_range.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity NullVectorRange is
    port (a : in std_logic_vector(0 downto 1); y : out std_logic);
end entity;
architecture rtl of NullVectorRange is
begin
    y <= '0';
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-NULL-VECTOR-RANGE"


def test_natural_generic_may_not_create_a_null_vector_range(tmp_path: Path) -> None:
    source = tmp_path / "generic_null_vector_range.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity GenericNullVectorRange is
    generic (WIDTH : natural := 4);
    port (a : in std_logic_vector(WIDTH - 1 downto 0); y : out std_logic);
end entity;
architecture rtl of GenericNullVectorRange is
begin
    y <= a(0);
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-NULL-VECTOR-RANGE"


def test_mixed_vector_integer_addition_is_rejected_before_width_promotion(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mixed_vector_integer_add.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
entity MixedVectorIntegerAdd is
    port (a : in signed(3 downto 0); y : out std_logic);
end entity;
architecture rtl of MixedVectorIntegerAdd is
begin
    y <= '1' when a + 1 < 0 else '0';
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-MIXED-ARITHMETIC-WIDTH"


def test_assignment_between_independent_generic_widths_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "independent_assignment_widths.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity IndependentAssignmentWidths is
    generic (A_WIDTH : positive := 4; Y_WIDTH : positive := 4);
    port (
        a : in std_logic_vector(A_WIDTH - 1 downto 0);
        y : out std_logic_vector(Y_WIDTH - 1 downto 0)
    );
end entity;
architecture rtl of IndependentAssignmentWidths is
begin
    y <= a;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-ASSIGNMENT-WIDTH"


def test_instance_port_default_generic_width_mismatch_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "instance_default_width_mismatch.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity WidthChild is
    generic (WIDTH : positive := 4);
    port (data : in std_logic_vector(WIDTH - 1 downto 0));
end entity;
architecture rtl of WidthChild is begin end architecture;

library ieee;
use ieee.std_logic_1164.all;
entity WidthTop is
    generic (TOP_WIDTH : positive := 8);
    port (data : in std_logic_vector(TOP_WIDTH - 1 downto 0));
end entity;
architecture structural of WidthTop is
begin
    u_child : entity work.WidthChild
        port map (data => data);
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-INSTANCE-PORT-WIDTH"


def test_instance_port_generic_override_proves_symbolic_width(
    tmp_path: Path,
) -> None:
    source = tmp_path / "instance_symbolic_width_match.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity WidthChild is
    generic (WIDTH : positive := 4);
    port (data : in std_logic_vector(WIDTH - 1 downto 0));
end entity;
architecture rtl of WidthChild is begin end architecture;

library ieee;
use ieee.std_logic_1164.all;
entity WidthTop is
    generic (TOP_WIDTH : positive := 8);
    port (data : in std_logic_vector(TOP_WIDTH - 1 downto 0));
end entity;
architecture structural of WidthTop is
begin
    u_child : entity work.WidthChild
        generic map (WIDTH => TOP_WIDTH)
        port map (data => data);
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert ".WIDTH(TOP_WIDTH)" in result.text


def test_vector_scalar_logical_broadcast_is_not_mistranslated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "vector_scalar_logic.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity VectorScalarLogic is
    port (
        a : in std_logic_vector(3 downto 0);
        b : in std_logic;
        y : out std_logic_vector(3 downto 0)
    );
end entity;
architecture rtl of VectorScalarLogic is
begin
    y <= a and b;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-VECTOR-LOGIC-WIDTH"


def test_mismatched_vector_logical_operands_are_not_extended(
    tmp_path: Path,
) -> None:
    source = tmp_path / "mismatched_vector_logic.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity MismatchedVectorLogic is
    port (
        a : in std_logic_vector(7 downto 0);
        b : in std_logic_vector(3 downto 0);
        y : out std_logic_vector(7 downto 0)
    );
end entity;
architecture rtl of MismatchedVectorLogic is
begin
    y <= a xor b;
end architecture;
""",
        encoding="utf-8",
    )

    with pytest.raises(SemanticError) as raised:
        convert_file(source, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-VECTOR-LOGIC-WIDTH"
    assert raised.value.diagnostic.file == str(source.resolve())
    assert raised.value.diagnostic.line == 12
    assert raised.value.diagnostic.column == 12


def test_literal_derived_four_state_equality_uses_exact_comparison(tmp_path: Path) -> None:
    source = tmp_path / "literal_derived_four_state.vhd"
    source.write_text(
        """library ieee;
use ieee.std_logic_1164.all;
entity LiteralDerivedFourState is
    port (y : out std_logic);
end entity;
architecture rtl of LiteralDerivedFourState is
begin
    y <= '1' when (not 'X') = 'X' else '0';
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "~1'bx === 1'bx ? 1'b1 : 1'b0" in result.text


def test_vector_multiply_is_rejected_without_explicit_result_width() -> None:
    fixture = Path(__file__).parents[1] / "fixtures" / "vhdl" / "m8_vector_multiply.vhd"

    with pytest.raises(SemanticError) as raised:
        convert_file(fixture, options=ConversionOptions(strict=True))

    assert raised.value.code == "HDLX-VHDL-VECTOR-ARITHMETIC-WIDTH"


def test_explicit_process_sensitivity_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "partial_sensitivity.vhd"
    source.write_text(
        """entity PartialSensitivity is
    port (a : in bit; b : in bit; y : out bit);
end entity;
architecture rtl of PartialSensitivity is
begin
    p : process(a)
    begin
        y <= a and b;
    end process;
end architecture;
""",
        encoding="utf-8",
    )

    result = convert_file(source, options=ConversionOptions(strict=True))

    assert "always @(a) begin : p" in result.text
    assert "always @(*)" not in result.text
