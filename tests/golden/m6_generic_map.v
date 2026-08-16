module M6GenericChild #(
    parameter integer WIDTH = 8,
    parameter ENABLE = 1'b1
) (
    input wire a,
    output wire y
);

assign y = a;

endmodule

module M6GenericTop (
    input wire a,
    output wire y
);

M6GenericChild #(
    .WIDTH(16),
    .ENABLE(1'b0)
) u_parameterized (
    .a(a),
    .y(y)
);

endmodule
