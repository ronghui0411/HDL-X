library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity M8SignedCompare is
    port (
        a : in signed(3 downto 0);
        y : out std_logic
    );
end entity;

architecture rtl of M8SignedCompare is
begin
    y <= '1' when a < "0001" else '0';
end architecture;
