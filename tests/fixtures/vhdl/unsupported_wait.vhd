library ieee;
use ieee.std_logic_1164.all;

entity UnsupportedWait is
    port (a : in std_logic);
end entity UnsupportedWait;

architecture rtl of UnsupportedWait is
begin
    process
    begin
        wait on a;
    end process;
end architecture rtl;
