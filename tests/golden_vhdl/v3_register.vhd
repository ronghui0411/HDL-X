library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3Register is
    port (
        clk : in std_logic;
        enable : in std_logic;
        d : in std_logic;
        q : out std_logic
    );
end entity V3Register;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3Register is
begin
    seq_p : process(clk)
    begin
        if rising_edge(clk) then
            if enable = '1' then
                q <= d;
            end if;
        end if;
    end process seq_p;
end architecture rtl;
