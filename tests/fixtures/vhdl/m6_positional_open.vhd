entity M6PositionalChild is
  generic (
    MODE : positive := 1
  );
  port (
    a : in bit;
    b : in bit;
    y : out bit
  );
end entity M6PositionalChild;

architecture rtl of M6PositionalChild is
begin
  y <= a and b;
end architecture rtl;

entity M6PositionalTop is
  port (
    a : in bit;
    b : in bit
  );
end entity M6PositionalTop;

architecture structural of M6PositionalTop is
begin
  u_positional : entity work.M6PositionalChild
    generic map (2)
    port map (a, b, open);
end architecture structural;
