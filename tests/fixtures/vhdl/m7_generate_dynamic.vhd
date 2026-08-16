entity M7GenerateDynamic is
    port (
        a : in bit;
        y : out bit
    );
end entity;

architecture rtl of M7GenerateDynamic is
begin
    g_bad : if a generate
        y <= a;
    end generate;
end architecture;
