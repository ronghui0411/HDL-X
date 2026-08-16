library ieee;
use ieee.std_logic_1164.all;

entity IfElseMux is
    port (
        a   : in std_logic;
        b   : in std_logic;
        sel : in std_logic;
        y   : out std_logic
    );
end entity IfElseMux;

architecture rtl of IfElseMux is
begin
    mux_p : process(a, b, sel)
    begin
        if sel = '1' then
            y <= a;
        else
            y <= b;
        end if;
    end process mux_p;
end architecture rtl;
