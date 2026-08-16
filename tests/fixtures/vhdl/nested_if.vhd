library ieee;
use ieee.std_logic_1164.all;

entity NestedIf is
    port (
        a    : in std_logic;
        b    : in std_logic;
        sel0 : in std_logic;
        sel1 : in std_logic;
        y    : out std_logic
    );
end entity NestedIf;

architecture rtl of NestedIf is
begin
    choose_p : process(a, b, sel0, sel1)
    begin
        if sel0 = '1' then
            if sel1 = '1' then
                y <= a;
            else
                y <= b;
            end if;
        elsif sel1 = '1' then
            y <= b;
        else
            y <= a;
        end if;
    end process choose_p;
end architecture rtl;
