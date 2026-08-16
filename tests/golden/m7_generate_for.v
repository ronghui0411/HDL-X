module M7GenerateFor #(
    parameter integer LANES = 4
) (
    input wire [LANES - 1:0] a,
    output wire [LANES - 1:0] y
);

genvar i;
generate
    // one generated cell per lane
    for (i = 0; i <= LANES - 1; i = i + 1) begin : g_lane
        assign y[i] = a[i];
    end
endgenerate

endmodule
