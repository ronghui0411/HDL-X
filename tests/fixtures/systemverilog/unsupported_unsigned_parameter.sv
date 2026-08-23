module UnsupportedUnsignedParameter #(
    parameter int unsigned WIDTH = 4
) (
    input  logic [WIDTH-1:0] a,
    output logic [WIDTH-1:0] y
);
    assign y = a;
endmodule
