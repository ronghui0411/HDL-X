module UnsupportedAlwaysCombNoTrigger (
    output logic y
);
    always_comb begin
        y = 1'b0;
    end
endmodule
