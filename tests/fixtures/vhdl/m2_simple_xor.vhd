library ieee;
use ieee.std_logic_1164.all;

entity M2SimpleXor is
    port (
        a : in std_logic;
        b : in std_logic;
        y : out std_logic
    );
end entity M2SimpleXor;

architecture rtl of M2SimpleXor is
begin
    y <= a xor b;
end architecture rtl;
