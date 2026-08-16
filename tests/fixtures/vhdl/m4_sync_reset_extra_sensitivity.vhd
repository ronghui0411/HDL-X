library ieee;
use ieee.std_logic_1164.all;

entity M4SyncResetExtraSensitivity is
  port (
    clk : in std_logic;
    reset : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4SyncResetExtraSensitivity is
begin
  seq_p : process (clk, reset)
  begin
    if rising_edge(clk) then
      if reset = '1' then
        q <= '0';
      else
        q <= d;
      end if;
    end if;
  end process;
end architecture;
