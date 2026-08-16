entity M6SimpleChild is
  port (
    a : in bit;
    y : out bit
  );
end entity M6SimpleChild;

architecture rtl of M6SimpleChild is
begin
  y <= a;
end architecture rtl;

entity M6SimpleTop is
  port (
    a : in bit;
    y : out bit
  );
end entity M6SimpleTop;

architecture structural of M6SimpleTop is
  signal child_a, child_y : bit;
begin
  child_a <= a;

  u_child : entity work.M6SimpleChild(rtl)
    port map (
      a => child_a,
      y => child_y
    );

  y <= child_y;
end architecture structural;
