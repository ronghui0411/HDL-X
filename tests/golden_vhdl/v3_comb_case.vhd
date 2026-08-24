library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity V3CombCase is
    port (
        a : in std_logic;
        b : in std_logic;
        enable : in std_logic;
        opcode : in unsigned(1 downto 0);
        y : out std_logic
    );
end entity V3CombCase;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

architecture rtl of V3CombCase is
begin
    comb_p : process(all)
        variable y_next : std_logic;
    begin
        y_next := y;
        if enable = '1' then
            case opcode is
                when "00" =>
                    y_next := a;
                when "01" =>
                    y_next := b;
                when others =>
                    y_next := a xor b;
            end case;
        else
            y_next := b;
        end if;
        y <= y_next;
    end process comb_p;
end architecture rtl;
