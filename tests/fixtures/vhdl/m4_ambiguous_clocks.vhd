library ieee;
use ieee.std_logic_1164.all;

entity M4AmbiguousClocks is
  port (
    clk_a : in std_logic;
    clk_b : in std_logic;
    reset : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4AmbiguousClocks is
begin
  seq_p : process (clk_a, clk_b, reset)
  begin
    if reset = '1' then
      q <= '0';
    elsif rising_edge(clk_a) then
      q <= d;
    elsif rising_edge(clk_b) then
      q <= d;
    end if;
  end process;
end architecture;
