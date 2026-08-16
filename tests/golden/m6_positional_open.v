module M6PositionalChild #(
    parameter integer MODE = 1
) (
    input wire a,
    input wire b,
    output wire y
);

assign y = a & b;

endmodule

module M6PositionalTop (
    input wire a,
    input wire b
);

M6PositionalChild #(
    2
) u_positional (
    a,
    b,
    /* open */
);

endmodule
