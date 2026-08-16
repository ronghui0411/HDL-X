library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity M4Counter is
  port (
    clk : in std_logic;
    reset_n : in std_logic;
    count : out unsigned(7 downto 0)
  );
end entity;

architecture rtl of M4Counter is
begin
  counter_p : process (clk)
  begin
    if rising_edge(clk) then
      if reset_n = '0' then
        count <= "00000000";
      else
        count <= count + 1;
      end if;
    end if;
  end process;
end architecture;
