module SvDeclarations #(
    parameter integer WIDTH = 4
) (
    input wire a,
    input wire b,
    input wire sel,
    input wire signed [WIDTH - 1:0] signed_a,
    input wire signed [WIDTH - 1:0] signed_b,
    output wire y,
    output reg signed [WIDTH - 1:0] signed_y
);

reg selected;
wire combined;
reg signed [WIDTH - 1:0] signed_sum;

assign combined = a & b;

always @(*) begin
    selected = sel ? combined : a;
    signed_sum = signed_a + signed_b;
    signed_y = signed_sum;
end

assign y = selected;

endmodule
