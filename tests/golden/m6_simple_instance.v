module M6SimpleChild (
    input wire a,
    output wire y
);

assign y = a;

endmodule

module M6SimpleTop (
    input wire a,
    output wire y
);

wire child_a;
wire child_y;

assign child_a = a;

M6SimpleChild u_child (
    .a(child_a),
    .y(child_y)
);

assign y = child_y;

endmodule
