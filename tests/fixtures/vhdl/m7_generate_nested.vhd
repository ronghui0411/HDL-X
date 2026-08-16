library ieee;
use ieee.std_logic_1164.all;

entity M7BitCell is
    port (
        a : in std_logic;
        y : out std_logic
    );
end entity M7BitCell;

architecture rtl of M7BitCell is
begin
    y <= a;
end architecture rtl;

library ieee;
use ieee.std_logic_1164.all;

entity M7GenerateNested is
    generic (
        LANES : positive := 4;
        ENABLE : boolean := true
    );
    port (
        a : in std_logic_vector(LANES - 1 downto 0);
        y : out std_logic_vector(LANES - 1 downto 0)
    );
end entity M7GenerateNested;

library ieee;
use ieee.std_logic_1164.all;

architecture structural of M7GenerateNested is
begin
    g_lane : for i in 0 to LANES - 1 generate
        signal local_value : std_logic;
    begin
        u_cell : entity work.M7BitCell(rtl)
            port map (
                a => a(i),
                y => local_value
            );

        g_enabled : if ENABLE generate
            y(i) <= local_value;
        else generate
            y(i) <= '0';
        end generate g_enabled;
    end generate g_lane;
end architecture structural;
