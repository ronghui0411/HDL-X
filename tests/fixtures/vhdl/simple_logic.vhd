library ieee;
use ieee.std_logic_1164.all;

entity SimpleLogic is
    port (
        a : in std_logic;
        b : in std_logic;
        y : out std_logic
    );
end entity SimpleLogic;

architecture rtl of SimpleLogic is
begin
    y <= (not a and b) xor a;
end architecture rtl;
