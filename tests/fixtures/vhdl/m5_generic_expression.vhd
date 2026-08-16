library ieee;
use ieee.std_logic_1164.all;

entity M5GenericExpression is
    generic (
        BASE_WIDTH  : positive := 4;
        EXTRA_WIDTH : natural := 2
    );
    port (
        data_in  : in  std_logic_vector(BASE_WIDTH + EXTRA_WIDTH * 2 - 1 downto 0);
        data_out : out std_logic_vector(BASE_WIDTH + EXTRA_WIDTH * 2 - 1 downto 0)
    );
end entity;

architecture rtl of M5GenericExpression is
begin
    data_out <= data_in;
end architecture;
