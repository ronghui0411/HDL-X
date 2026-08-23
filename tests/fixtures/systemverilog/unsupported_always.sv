module UnsupportedAlways(input logic a, output logic y);
    always @(*) y = a;
endmodule
