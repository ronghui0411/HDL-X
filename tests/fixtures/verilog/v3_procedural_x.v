module V3ProceduralX (
    input wire enable,
    output reg y
);
always @(*) begin
    if (enable)
        y = 1'b1;
    else
        y = 1'bx;
end
endmodule
