entity M7GenerateIf is
    generic (
        ENABLE : boolean := true
    );
    port (
        a : in bit;
        b : in bit;
        y : out bit
    );
end entity M7GenerateIf;

architecture rtl of M7GenerateIf is
begin
    g_choice : if ENABLE generate
        y <= a;
    else generate
        y <= b;
    end generate g_choice;
end architecture rtl;
