library ieee;
use ieee.std_logic_1164.all;

entity M4ClockEnable is
  port (
    clk : in std_logic;
    enable : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4ClockEnable is
begin
  seq_p : process (clk)
  begin
    if rising_edge(clk) then
      if enable = '1' then
        q <= d;
      end if;
    end if;
  end process;
end architecture;
