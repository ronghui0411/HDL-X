entity M6ComponentChild is
  port (
    a : in bit;
    y : out bit
  );
end entity M6ComponentChild;

architecture rtl of M6ComponentChild is
begin
  y <= a;
end architecture rtl;

entity M6ComponentTop is
  port (
    a : in bit;
    y : out bit
  );
end entity M6ComponentTop;

architecture structural of M6ComponentTop is
  component M6ComponentChild
    port (
      a : in bit;
      y : out bit
    );
  end component;

  signal first_y, second_y : bit;
begin
  u_first : M6ComponentChild
    port map (
      a => a,
      y => first_y
    );

  u_second : M6ComponentChild
    port map (
      a => first_y,
      y => second_y
    );

  y <= second_y;
end architecture structural;
