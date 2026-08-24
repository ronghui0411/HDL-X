library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3IfGenerate is
    generic (
        ENABLE : integer := 1
    );
    port (
        a : in std_logic;
        y : out std_logic
    );
end entity V3IfGenerate;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3IfGenerate is
begin
    g_enabled : if ENABLE /= 0 generate
    begin
        y <= a;
    end generate g_enabled;
end architecture rtl;
