module M6ComponentChild (
    input wire a,
    output wire y
);

assign y = a;

endmodule

module M6ComponentTop (
    input wire a,
    output wire y
);

wire first_y;
wire second_y;

M6ComponentChild u_first (
    .a(a),
    .y(first_y)
);

M6ComponentChild u_second (
    .a(first_y),
    .y(second_y)
);

assign y = second_y;

endmodule
