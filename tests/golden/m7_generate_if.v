module M7GenerateIf #(
    parameter ENABLE = 1'b1
) (
    input wire a,
    input wire b,
    output wire y
);

generate
    if (ENABLE) begin : g_choice
        assign y = a;
    end else begin : g_choice
        assign y = b;
    end
endgenerate

endmodule
