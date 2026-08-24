library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3ProceduralX is
    port (
        enable : in std_logic;
        y : out std_logic
    );
end entity V3ProceduralX;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3ProceduralX is
begin
    comb_process_1 : process(all)
        variable y_next : std_logic;
    begin
        y_next := y;
        if enable = '1' then
            y_next := '1';
        else
            y_next := 'X';
        end if;
        y <= y_next;
    end process comb_process_1;
end architecture rtl;
