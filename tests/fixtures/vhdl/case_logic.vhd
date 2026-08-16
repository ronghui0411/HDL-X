library ieee;
use ieee.std_logic_1164.all;

entity CaseLogic is
    port (
        a   : in std_logic;
        b   : in std_logic;
        sel : in std_logic_vector(1 downto 0);
        y   : out std_logic
    );
end entity CaseLogic;

architecture rtl of CaseLogic is
begin
    case_p : process(a, b, sel)
    begin
        case sel is
            when "00" => y <= a;
            when "01" => y <= b;
            when others => y <= '0';
        end case;
    end process case_p;
end architecture rtl;
