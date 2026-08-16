library ieee;
use ieee.std_logic_1164.all;

entity M4MultiRegister is
  port (
    clk : in std_logic;
    reset_n : in std_logic;
    d : in std_logic;
    qa : out std_logic;
    qb : out std_logic
  );
end entity;

architecture rtl of M4MultiRegister is
begin
  registers_p : process (clk, reset_n)
  begin
    if reset_n = '0' then
      qa <= '0';
      qb <= '0';
    elsif rising_edge(clk) then
      qa <= d;
      qb <= qa;
    end if;
  end process;
end architecture;
