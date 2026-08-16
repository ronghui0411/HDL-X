module M7BitCell (
    input wire a,
    output wire y
);

assign y = a;

endmodule

module M7GenerateNested #(
    parameter integer LANES = 4,
    parameter ENABLE = 1'b1
) (
    input wire [LANES - 1:0] a,
    output wire [LANES - 1:0] y
);

genvar i;
generate
    for (i = 0; i <= LANES - 1; i = i + 1) begin : g_lane
        wire local_value;
        M7BitCell u_cell (
            .a(a[i]),
            .y(local_value)
        );
        if (ENABLE) begin : g_enabled
            assign y[i] = local_value;
        end else begin : g_enabled
            assign y[i] = 1'b0;
        end
    end
endgenerate

endmodule
