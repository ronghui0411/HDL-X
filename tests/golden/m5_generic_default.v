module M5GenericDefault #(
    parameter integer DEPTH = 16,
    parameter integer INIT_VALUE = 3
) (
    input wire data_in,
    output wire data_out
);

assign data_out = data_in;

endmodule
