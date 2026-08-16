library ieee;
use ieee.std_logic_1164.all;

entity M2SimpleOr is
    port (
        a : in std_logic;
        b : in std_logic;
        y : out std_logic
    );
end entity M2SimpleOr;

architecture rtl of M2SimpleOr is
begin
    y <= a or b;
end architecture rtl;
