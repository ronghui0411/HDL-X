entity M7GenerateUnresolved is
    port (y : out bit);
end entity;

architecture rtl of M7GenerateUnresolved is
begin
    g_bad : for i in 0 to 1 generate
        signal local_value : bit;
    begin
        local_value <= missing_name;
        y <= local_value;
    end generate;
end architecture;
