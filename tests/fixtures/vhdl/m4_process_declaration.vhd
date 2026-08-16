library ieee;
use ieee.std_logic_1164.all;

entity M4ProcessDeclaration is
  port (clk : in std_logic; q : out std_logic);
end entity;

architecture rtl of M4ProcessDeclaration is
begin
  seq_p : process (clk)
    constant C : std_logic := '1';
  begin
    if rising_edge(clk) then
      q <= C;
    end if;
  end process;
end architecture;
