library ieee;
use ieee.std_logic_1164.all;

entity M2VectorAssignment is
    port (
        a : in std_logic_vector(7 downto 0);
        y : out std_logic_vector(7 downto 0)
    );
end entity M2VectorAssignment;

architecture rtl of M2VectorAssignment is
begin
    y <= a;
end architecture rtl;
