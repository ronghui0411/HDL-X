library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity M8VectorMultiply is
    port (
        a : in unsigned(3 downto 0);
        b : in unsigned(3 downto 0);
        y : out unsigned(7 downto 0)
    );
end entity;

architecture rtl of M8VectorMultiply is
begin
    y <= a * b;
end architecture;
