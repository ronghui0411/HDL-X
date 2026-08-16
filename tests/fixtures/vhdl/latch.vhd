library ieee;
use ieee.std_logic_1164.all;

entity LatchExample is
    port (
        d  : in std_logic;
        en : in std_logic;
        q  : out std_logic
    );
end entity LatchExample;

architecture rtl of LatchExample is
begin
    latch_p : process(d, en)
    begin
        if en = '1' then
            q <= d;
        end if;
    end process latch_p;
end architecture rtl;
