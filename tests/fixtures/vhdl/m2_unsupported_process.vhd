library ieee;
use ieee.std_logic_1164.all;

entity M2UnsupportedProcess is
    port (
        a : in std_logic;
        y : out std_logic
    );
end entity M2UnsupportedProcess;

architecture rtl of M2UnsupportedProcess is
begin
    process (a)
    begin
        y <= a;
    end process;
end architecture rtl;
