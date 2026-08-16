library ieee;
use ieee.std_logic_1164.all;

entity UnsupportedProcessDelay is
    port (a : in std_logic; y : out std_logic);
end entity UnsupportedProcessDelay;

architecture rtl of UnsupportedProcessDelay is
begin
    process(a)
    begin
        y <= a after 1 ns;
    end process;
end architecture rtl;
