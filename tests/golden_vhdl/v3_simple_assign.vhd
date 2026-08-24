library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3SimpleAssign is
    port (
        a : in std_logic;
        b : in std_logic;
        y : out std_logic
    );
end entity V3SimpleAssign;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3SimpleAssign is
begin
    y <= a and b;
end architecture rtl;
