-- commented module
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3Comments is
    port (
        -- input a docs
        a : in std_logic;
        -- input a trailing
        b : in std_logic;
        y : out std_logic
    );
end entity V3Comments;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3Comments is
begin
    -- combinational process
    comb_process_1 : process(all)
        variable y_next : std_logic;
    begin
        y_next := y;
        -- branch docs
        if a = '1' then
            y_next := b;
            -- true assignment
        else
            -- false assignment
            y_next := '0';
        end if;
        y <= y_next;
    end process comb_process_1;
end architecture rtl;
