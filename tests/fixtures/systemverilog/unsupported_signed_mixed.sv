module UnsupportedSignedMixed (
    input  logic signed [7:0] signed_value,
    input  logic        [7:0] unsigned_value,
    output logic signed [7:0] result
);
    assign result = signed_value + unsigned_value;
endmodule
