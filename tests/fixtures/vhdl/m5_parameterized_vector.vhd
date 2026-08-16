library ieee;
use ieee.std_logic_1164.all;

entity M5ParameterizedVector is
    generic (
        WIDTH : positive := 12
    );
    port (
        desc_in  : in  std_logic_vector(WIDTH - 1 downto 0);
        asc_in   : in  std_logic_vector(0 to WIDTH - 1);
        desc_out : out std_logic_vector(WIDTH - 1 downto 0);
        asc_out  : out std_logic_vector(0 to WIDTH - 1)
    );
end entity;

architecture rtl of M5ParameterizedVector is
begin
    desc_out <= desc_in;
    asc_out  <= asc_in;
end architecture;
