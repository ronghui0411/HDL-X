module V3IfGenerate #(parameter ENABLE = 1) (
  input wire a,
  output wire y
);
  generate
    if (ENABLE) begin : g_enabled
      assign y = a;
    end
  endgenerate
endmodule
