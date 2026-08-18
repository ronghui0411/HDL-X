library ieee;
use ieee.std_logic_1164.all;

entity V01SeqResetEnable is
  port (
    clk : in std_logic;
    reset_n : in std_logic;
    enable : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of V01SeqResetEnable is
begin
  state_p : process (clk, reset_n)
  begin
    if reset_n = '0' then
      q <= '0';
    elsif rising_edge(clk) then
      if enable = '1' then
        q <= d;
      end if;
    end if;
  end process;
end architecture;
