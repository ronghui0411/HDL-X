library ieee;
use ieee.std_logic_1164.all;

entity M2SimpleExpression is
    port (
        a : in std_logic;
        b : in std_logic;
        c : in std_logic;
        d : in std_logic;
        y : out std_logic
    );
end entity M2SimpleExpression;

architecture rtl of M2SimpleExpression is
begin
    y <= (not a and b) or (c xor d);
end architecture rtl;
