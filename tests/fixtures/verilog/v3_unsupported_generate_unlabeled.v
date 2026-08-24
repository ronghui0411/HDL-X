module V3UnsupportedGenerateUnlabeled #(parameter WIDTH = 2) (
  input wire [WIDTH-1:0] a,
  output wire [WIDTH-1:0] y
);
  genvar i;
  generate
    for (i = 0; i < WIDTH; i = i + 1)
      assign y[i] = a[i];
  endgenerate
endmodule
