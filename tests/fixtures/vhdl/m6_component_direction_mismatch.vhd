entity M6DirectionChild is
  port (
    a : in bit;
    y : out bit
  );
end entity M6DirectionChild;

architecture rtl of M6DirectionChild is
begin
  y <= a;
end architecture rtl;

entity M6DirectionTop is
end entity M6DirectionTop;

architecture structural of M6DirectionTop is
  component M6DirectionChild
    port (
      a : out bit;
      y : out bit
    );
  end component;

  signal component_a, component_y : bit;
begin
  u_child : M6DirectionChild
    port map (
      a => component_a,
      y => component_y
    );
end architecture structural;
