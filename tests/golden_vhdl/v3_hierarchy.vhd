library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3Child is
    generic (
        WIDTH : integer := 4
    );
    port (
        a : in unsigned(WIDTH - 1 downto 0);
        y : out unsigned(WIDTH - 1 downto 0)
    );
end entity V3Child;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3Child is
begin
    y <= a;
end architecture rtl;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3Hierarchy is
    generic (
        WIDTH : integer := 4
    );
    port (
        a : in unsigned(WIDTH - 1 downto 0);
        y : out unsigned(WIDTH - 1 downto 0)
    );
end entity V3Hierarchy;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3Hierarchy is
    signal middle : unsigned(WIDTH - 1 downto 0);
begin
    u_named : entity work.V3Child
        generic map (
            WIDTH => WIDTH
        )
        port map (
            a => a,
            y => middle
        );
    u_positional : entity work.V3Child
        generic map (
            WIDTH
        )
        port map (
            middle,
            y
        );
end architecture rtl;
