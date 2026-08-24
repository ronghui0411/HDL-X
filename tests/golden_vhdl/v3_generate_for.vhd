library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3Generate is
    generic (
        WIDTH : integer := 4
    );
    port (
        a : in unsigned(WIDTH - 1 downto 0);
        y : out unsigned(WIDTH - 1 downto 0)
    );
end entity V3Generate;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3Generate is
begin
    -- per-bit hierarchy
    g_bit : for i in 0 to WIDTH - 1 generate
        -- local generated signal
        signal local_value : std_logic;
    begin
        local_value <= a(i);
        y(i) <= local_value;
    end generate g_bit;
end architecture rtl;
