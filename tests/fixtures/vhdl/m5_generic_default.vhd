library ieee;
use ieee.std_logic_1164.all;

entity M5GenericDefault is
    generic (
        DEPTH      : natural := 16;
        INIT_VALUE : integer := 3
    );
    port (
        data_in  : in  std_logic;
        data_out : out std_logic
    );
end entity;

architecture rtl of M5GenericDefault is
begin
    data_out <= data_in;
end architecture;
