module SvChild #(
    parameter int WIDTH = 4
) (
    input  wire [WIDTH-1:0] a,
    output wire [WIDTH-1:0] y
);
    assign y = a;
endmodule

module SvTop #(
    parameter int WIDTH = 4
) (
    input  wire [WIDTH-1:0] a,
    output wire [WIDTH-1:0] named_y,
    output wire [WIDTH-1:0] positional_y
);
    SvChild #(.WIDTH(WIDTH)) u_named (
        .a(a),
        .y(named_y)
    );

    SvChild #(WIDTH) u_positional (a, positional_y);
endmodule
