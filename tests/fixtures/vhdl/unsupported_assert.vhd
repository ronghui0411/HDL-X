library ieee;
use ieee.std_logic_1164.all;

entity UnsupportedAssert is
    port (a : in std_logic; y : out std_logic);
end entity UnsupportedAssert;

architecture rtl of UnsupportedAssert is
begin
    process(a)
    begin
        assert a = '1';
        y <= a;
    end process;
end architecture rtl;
