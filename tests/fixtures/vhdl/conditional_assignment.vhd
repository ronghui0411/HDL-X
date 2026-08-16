library ieee;
use ieee.std_logic_1164.all;

entity ConditionalAssignment is
    port (
        a   : in std_logic;
        b   : in std_logic;
        sel : in std_logic;
        y   : out std_logic
    );
end entity ConditionalAssignment;

architecture rtl of ConditionalAssignment is
begin
    y <= a when sel = '1' else b;
end architecture rtl;
