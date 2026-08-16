module M5MultiGeneric #(
    parameter integer WORD_WIDTH = 8,
    parameter integer LANES = 4,
    parameter integer TOTAL_WIDTH = WORD_WIDTH * LANES
) (
    input wire [TOTAL_WIDTH - 1:0] data_in,
    output wire [TOTAL_WIDTH - 1:0] data_out
);

assign data_out = data_in;

endmodule
