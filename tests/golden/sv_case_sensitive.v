module SvCaseSensitive (
    input wire data,
    input wire Data,
    output wire y
);

assign y = data ^ Data;

endmodule
