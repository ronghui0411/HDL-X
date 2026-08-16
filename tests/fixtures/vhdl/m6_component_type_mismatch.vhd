entity M6TypeChild is
  port (
    a : in bit;
    y : out bit
  );
end entity M6TypeChild;

architecture rtl of M6TypeChild is
begin
  y <= a;
end architecture rtl;

entity M6TypeTop is
end entity M6TypeTop;

architecture structural of M6TypeTop is
  component M6TypeChild
    port (
      a : in boolean;
      y : out bit
    );
  end component;

  signal component_a : boolean;
  signal component_y : bit;
begin
  u_child : M6TypeChild
    port map (
      a => component_a,
      y => component_y
    );
end architecture structural;
