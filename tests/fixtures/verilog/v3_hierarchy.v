module V3Child #(
    parameter WIDTH = 4
) (
    input wire [WIDTH-1:0] a,
    output wire [WIDTH-1:0] y
);
assign y = a;
endmodule

module V3Hierarchy #(
    parameter WIDTH = 4
) (
    input wire [WIDTH-1:0] a,
    output wire [WIDTH-1:0] y
);
wire [WIDTH-1:0] middle;

V3Child #(.WIDTH(WIDTH)) u_named (
    .a(a),
    .y(middle)
);
V3Child #(WIDTH) u_positional (
    middle,
    y
);
endmodule
