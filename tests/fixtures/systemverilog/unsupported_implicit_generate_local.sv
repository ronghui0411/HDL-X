module UnsupportedImplicitGenerateLocal #(
    parameter int WIDTH = 2
) (
    input  logic [WIDTH-1:0] a,
    output logic [WIDTH-1:0] y
);
    for (genvar index = 0; index < WIDTH; index++) begin : gen_bits
        logic local_value;
        assign local_value = a[index];
        assign y[index] = local_value;
    end
endmodule
