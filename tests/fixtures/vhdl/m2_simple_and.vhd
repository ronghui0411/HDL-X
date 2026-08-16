library ieee;
use ieee.std_logic_1164.all;

--! Simple AND gate
entity M2SimpleAnd is
    port (
        a : in std_logic; -- left operand
        b : in std_logic;
        y : out std_logic
    );
end entity M2SimpleAnd;

architecture rtl of M2SimpleAnd is
begin
    -- drive the result
    y <= a and b;
end architecture rtl;
