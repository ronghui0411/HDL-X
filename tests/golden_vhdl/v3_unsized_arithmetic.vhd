library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3UnsizedArithmetic is
    port (
        a : in unsigned(3 downto 0);
        y : out unsigned(3 downto 0)
    );
end entity V3UnsizedArithmetic;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3UnsizedArithmetic is
begin
    y <= a + 1;
end architecture rtl;
