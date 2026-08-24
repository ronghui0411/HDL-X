module V3UnsupportedMixedEvent (
    input wire clk,
    input wire enable,
    input wire d,
    output reg q
);
always @(posedge clk or enable)
    q <= d;
endmodule
