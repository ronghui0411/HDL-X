module V3UnsupportedWidthSizing (
    input wire [7:0] a,
    input wire [7:0] b,
    output wire [3:0] y
);
assign y = a + b;
endmodule
