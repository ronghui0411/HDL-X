module SvCaseSensitive (
    input  logic data,
    input  logic Data,
    output wire  y
);
    assign y = data ^ Data;
endmodule
