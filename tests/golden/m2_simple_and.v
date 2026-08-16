/// Simple AND gate
module M2SimpleAnd (
    input wire a,
    // left operand
    input wire b,
    output wire y
);

// drive the result
assign y = a & b;

endmodule
