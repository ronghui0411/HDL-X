module UnsupportedGenerate #(parameter int WIDTH = 2) (
    input  logic [WIDTH-1:0] a,
    output logic [WIDTH-1:0] y
);
    generate
        for (genvar index = 0; index < WIDTH; index++) begin : gen_bits
            assign y[index] = a[index];
        end
    endgenerate
endmodule
