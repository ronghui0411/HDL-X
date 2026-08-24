module V3UnsupportedAlwaysComb (
    input wire a,
    output reg y
);
always_comb y = a;
endmodule
