library ieee;
use ieee.std_logic_1164.all;

entity M7GenerateDownto is
    port (
        a : in std_logic_vector(3 downto 0);
        y : out std_logic_vector(3 downto 0)
    );
end entity M7GenerateDownto;

architecture rtl of M7GenerateDownto is
begin
    g_bit : for i in 3 downto 0 generate
        y(i) <= a(i);
    end generate g_bit;
end architecture rtl;
