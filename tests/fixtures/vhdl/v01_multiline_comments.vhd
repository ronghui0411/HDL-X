library ieee;
use ieee.std_logic_1164.all;

entity V01MultilineComments is
  generic (ENABLE : boolean := true);
  port (
    a : in std_logic;
    b : in std_logic;
    y : out std_logic;
    z : out std_logic;
    w : out std_logic
  );
end entity;

architecture rtl of V01MultilineComments is
  signal unused_signal :
    std_logic; -- declaration tail
begin
  y <=
    a and
    b; -- assignment tail

  comb_p : process (
    a,
    b
  )
  begin
    z <=
      a or
      b;
  end process; -- process tail

  g_enabled : if ENABLE generate
  begin
    w <=
      a xor
      b;
  end generate; -- generate tail
end architecture;
