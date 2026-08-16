library ieee;
use ieee.std_logic_1164.all;

entity M2UnsupportedDelay is
    port (
        a : in std_logic;
        y : out std_logic
    );
end entity M2UnsupportedDelay;

architecture rtl of M2UnsupportedDelay is
begin
    y <= a after 1 ns;
end architecture rtl;
