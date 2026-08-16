library ieee;
use ieee.std_logic_1164.all;

entity M5GenericWidth is
    generic (
        WIDTH : positive := 8
    );
    port (
        data_in  : in  std_logic_vector(WIDTH - 1 downto 0);
        data_out : out std_logic_vector(WIDTH - 1 downto 0)
    );
end entity;

architecture rtl of M5GenericWidth is
begin
    data_out <= data_in;
end architecture;
