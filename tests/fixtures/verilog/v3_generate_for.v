module V3Generate #(parameter WIDTH = 4) (
  input wire [WIDTH-1:0] a,
  output wire [WIDTH-1:0] y
);
  genvar i;
  generate
    // per-bit hierarchy
    for (i = 0; i < WIDTH; i = i + 1) begin : g_bit
      // local generated signal
      wire local_value;
      assign local_value = a[i];
      assign y[i] = local_value;
    end
  endgenerate
endmodule
