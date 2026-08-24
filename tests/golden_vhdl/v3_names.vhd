library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity entity_hdl_x is
    port (
        process_hdl_x : in std_logic;
        Data : in std_logic;
        data_2 : in std_logic;
        result : out std_logic
    );
end entity entity_hdl_x;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of entity_hdl_x is
begin
    result <= process_hdl_x and Data and data_2;
end architecture rtl;
