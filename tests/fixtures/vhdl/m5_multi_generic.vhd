library ieee;
use ieee.std_logic_1164.all;

entity M5MultiGeneric is
    generic (
        WORD_WIDTH  : positive := 8;
        LANES       : positive := 4;
        TOTAL_WIDTH : positive := WORD_WIDTH * LANES
    );
    port (
        data_in  : in  std_logic_vector(TOTAL_WIDTH - 1 downto 0);
        data_out : out std_logic_vector(TOTAL_WIDTH - 1 downto 0)
    );
end entity;

architecture rtl of M5MultiGeneric is
begin
    data_out <= data_in;
end architecture;
