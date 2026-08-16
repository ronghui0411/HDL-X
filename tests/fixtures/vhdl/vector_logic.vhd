library ieee;
use ieee.std_logic_1164.all;

entity VectorLogic is
    generic (
        WIDTH : positive := 8
    );
    port (
        a : in std_logic_vector(WIDTH - 1 downto 0);
        b : in std_logic_vector(0 to WIDTH - 1);
        y : out std_logic_vector(WIDTH - 1 downto 0)
    );
end entity VectorLogic;

architecture rtl of VectorLogic is
begin
    y <= a xor not b;
end architecture rtl;
