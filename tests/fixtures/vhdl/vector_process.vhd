library ieee;
use ieee.std_logic_1164.all;

entity VectorProcess is
    port (
        a : in std_logic_vector(7 downto 0);
        b : in std_logic_vector(7 downto 0);
        y : out std_logic_vector(7 downto 0)
    );
end entity VectorProcess;

architecture rtl of VectorProcess is
begin
    logic_p : process(a, b)
    begin
        y <= (a and b) xor not a;
    end process logic_p;
end architecture rtl;
