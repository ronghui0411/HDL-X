entity M7GenerateUnsupported is
    generic (
        SELECTOR : natural := 0
    );
    port (
        y : out bit
    );
end entity M7GenerateUnsupported;

architecture rtl of M7GenerateUnsupported is
begin
    g_case : case SELECTOR generate
        when 0 =>
            y <= '0';
        when others =>
            y <= '1';
    end generate g_case;
end architecture rtl;
