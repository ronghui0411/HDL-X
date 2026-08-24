module V3UnsupportedTristate (
    input wire enable,
    input wire a,
    output wire y
);
assign y = enable ? a : 1'bz;
endmodule
