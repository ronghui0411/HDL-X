library ieee;
use ieee.std_logic_1164.all;

entity M4LevelCondition is
  port (
    clk : in std_logic;
    d : in std_logic;
    q : out std_logic
  );
end entity;

architecture rtl of M4LevelCondition is
begin
  level_p : process (clk, d)
  begin
    if clk = '1' then
      q <= d;
    end if;
  end process;
end architecture;
