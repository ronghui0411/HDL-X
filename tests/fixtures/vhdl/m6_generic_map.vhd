entity M6GenericChild is
  generic (
    WIDTH : positive := 8;
    ENABLE : boolean := true
  );
  port (
    a : in bit;
    y : out bit
  );
end entity M6GenericChild;

architecture rtl of M6GenericChild is
begin
  y <= a;
end architecture rtl;

entity M6GenericTop is
  port (
    a : in bit;
    y : out bit
  );
end entity M6GenericTop;

architecture structural of M6GenericTop is
begin
  u_parameterized : entity work.M6GenericChild
    generic map (
      WIDTH => 16,
      ENABLE => false
    )
    port map (
      a => a,
      y => y
    );
end architecture structural;
