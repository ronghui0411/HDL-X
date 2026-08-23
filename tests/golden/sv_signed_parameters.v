module SvSignedParams #(
    parameter integer WIDTH = 4,
    parameter integer OUT_WIDTH = WIDTH + 1
) (
    input wire signed [WIDTH - 1:0] a,
    input wire signed [WIDTH - 1:0] b,
    output reg signed [OUT_WIDTH - 1:0] y,
    output reg negative
);

always @(*) begin : signed_comb
    y = a + b;
    negative = a < 0;
end

endmodule
