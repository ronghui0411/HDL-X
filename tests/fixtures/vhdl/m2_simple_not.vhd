library ieee;
use ieee.std_logic_1164.all;

entity M2SimpleNot is
    port (
        a : in std_logic;
        y : out std_logic
    );
end entity M2SimpleNot;

architecture rtl of M2SimpleNot is
begin
    y <= not a;
end architecture rtl;
