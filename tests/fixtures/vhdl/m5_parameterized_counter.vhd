library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity M5ParameterizedCounter is
    generic (
        WIDTH : positive := 8
    );
    port (
        clk   : in  std_logic;
        count : out unsigned(WIDTH - 1 downto 0)
    );
end entity;

architecture rtl of M5ParameterizedCounter is
begin
    counter_p : process (clk)
    begin
        if rising_edge(clk) then
            count <= count + 1;
        end if;
    end process;
end architecture;
