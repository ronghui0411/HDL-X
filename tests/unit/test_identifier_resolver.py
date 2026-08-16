from hdl_x.transformer.identifier_resolver import IdentifierResolver, NameStyle


def test_preserves_legal_public_name() -> None:
    resolver = IdentifierResolver()

    assert resolver.resolve("DataOut") == "DataOut"


def test_vhdl_lookup_is_case_insensitive() -> None:
    resolver = IdentifierResolver()

    assert resolver.resolve("DataOut") == resolver.resolve("dataout")


def test_reserved_keyword_is_renamed_deterministically() -> None:
    resolver = IdentifierResolver()

    assert resolver.resolve("module") == "module_hdl_x"
    assert resolver.resolve("MODULE") == "module_hdl_x"


def test_illegal_identifier_is_sanitized() -> None:
    resolver = IdentifierResolver()

    assert resolver.resolve("1-data") == "hdl_x_1_data"


def test_style_conversion_is_explicit() -> None:
    resolver = IdentifierResolver(NameStyle.SNAKE_CASE)

    assert resolver.resolve("DataOutput") == "data_output"
