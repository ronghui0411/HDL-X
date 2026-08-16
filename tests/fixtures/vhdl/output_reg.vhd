library ieee;
use ieee.std_logic_1164.all;

entity OutputReg is
    port (
        a : in std_logic;
        b : in std_logic;
        y : out std_logic
    );
end entity OutputReg;

architecture rtl of OutputReg is
begin
    output_p : process(a, b)
    begin
        y <= a or b;
    end process output_p;
end architecture rtl;
