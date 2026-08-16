module M5ParameterizedVector #(
    parameter integer WIDTH = 12
) (
    input wire [WIDTH - 1:0] desc_in,
    input wire [0:WIDTH - 1] asc_in,
    output wire [WIDTH - 1:0] desc_out,
    output wire [0:WIDTH - 1] asc_out
);

assign desc_out = desc_in;

assign asc_out = asc_in;

endmodule
