module SvSignedParams #(
    parameter int WIDTH = 4,
    parameter int OUT_WIDTH = WIDTH + 1
) (
    input  logic signed [WIDTH-1:0]     a,
    input  logic signed [WIDTH-1:0]     b,
    output logic signed [OUT_WIDTH-1:0] y,
    output logic                        negative
);
    always_comb begin : signed_comb
        y = a + b;
        negative = a < 0;
    end
endmodule
