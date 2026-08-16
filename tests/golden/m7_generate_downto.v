module M7GenerateDownto (
    input wire [3:0] a,
    output wire [3:0] y
);

genvar i;
generate
    for (i = 3; i >= 0; i = i - 1) begin : g_bit
        assign y[i] = a[i];
    end
endgenerate

endmodule
