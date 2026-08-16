entity M6DefaultChild is
  generic (
    WIDTH : positive := 8
  );
  port (
    a : in bit;
    y : out bit
  );
end entity M6DefaultChild;

architecture rtl of M6DefaultChild is
begin
  y <= a;
end architecture rtl;

entity M6DefaultTop is
end entity M6DefaultTop;

architecture structural of M6DefaultTop is
  component M6DefaultChild
    generic (
      WIDTH : positive := 4
    );
    port (
      a : in bit;
      y : out bit
    );
  end component;

  signal component_a, component_y : bit;
begin
  u_child : M6DefaultChild
    port map (
      a => component_a,
      y => component_y
    );
end architecture structural;
