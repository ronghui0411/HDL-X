library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3IntegerCounter is
    port (
        clk : in std_logic;
        rst : in std_logic;
        count : out signed(31 downto 0)
    );
end entity V3IntegerCounter;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3IntegerCounter is
begin
    seq_process_1 : process(clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                count <= to_signed(0, count'length);
            else
                count <= count + 1;
            end if;
        end if;
    end process seq_process_1;
end architecture rtl;
