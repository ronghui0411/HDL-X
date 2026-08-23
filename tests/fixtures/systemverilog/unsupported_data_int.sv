module UnsupportedDataInt (
    input  int value,
    output logic y
);
    assign y = value[0];
endmodule
