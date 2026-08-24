library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3SignedParameter is
    generic (
        WIDTH : integer := 8
    );
    port (
        a : in signed(WIDTH - 1 downto 0);
        b : in signed(WIDTH - 1 downto 0);
        y : out signed(WIDTH - 1 downto 0)
    );
end entity V3SignedParameter;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3SignedParameter is
begin
    y <= a + b;
end architecture rtl;
