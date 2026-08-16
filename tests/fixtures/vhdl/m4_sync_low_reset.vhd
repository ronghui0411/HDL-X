library ieee;
use ieee.std_logic_1164.all;

entity M4SyncLowReset is
  port (
    clk : in std_logic;
    reset_n : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4SyncLowReset is
begin
  seq_p : process (clk)
  begin
    if falling_edge(clk) then
      if reset_n = '0' then
        q <= '0';
      else
        q <= d;
      end if;
    end if;
  end process;
end architecture;
