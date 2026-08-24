module V3UnsupportedGenerateElse #(parameter ENABLE = 1) (
  input wire a,
  output wire y
);
  generate
    if (ENABLE) begin : g_on
      assign y = a;
    end else begin : g_off
      assign y = 1'b0;
    end
  endgenerate
endmodule
