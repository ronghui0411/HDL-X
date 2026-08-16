library ieee;
use ieee.std_logic_1164.all;

entity M7GenerateFor is
    generic (
        LANES : positive := 4
    );
    port (
        a : in std_logic_vector(LANES - 1 downto 0);
        y : out std_logic_vector(LANES - 1 downto 0)
    );
end entity M7GenerateFor;

architecture rtl of M7GenerateFor is
begin
    -- one generated cell per lane
    g_lane : for i in 0 to LANES - 1 generate
        y(i) <= a(i);
    end generate g_lane;
end architecture rtl;
