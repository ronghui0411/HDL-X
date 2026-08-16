module M5GenericExpression #(
    parameter integer BASE_WIDTH = 4,
    parameter integer EXTRA_WIDTH = 2
) (
    input wire [BASE_WIDTH + EXTRA_WIDTH * 2 - 1:0] data_in,
    output wire [BASE_WIDTH + EXTRA_WIDTH * 2 - 1:0] data_out
);

assign data_out = data_in;

endmodule
