library ieee;
use ieee.std_logic_1164.all;

entity M4AsyncLowReset is
  port (
    clk : in std_logic;
    reset_n : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4AsyncLowReset is
begin
  seq_p : process (reset_n, clk)
  begin
    if reset_n = '0' then
      q <= '0';
    elsif falling_edge(clk) then
      q <= d;
    end if;
  end process;
end architecture;
