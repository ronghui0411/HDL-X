entity M7GenerateElsif is
    generic (
        SELECTOR : natural := 0
    );
    port (
        a : in bit;
        b : in bit;
        y : out bit
    );
end entity M7GenerateElsif;

architecture rtl of M7GenerateElsif is
begin
    g_choice : if SELECTOR = 0 generate
        y <= a;
    elsif SELECTOR = 1 generate
        y <= b;
    else generate
        y <= '0';
    end generate g_choice;
end architecture rtl;
