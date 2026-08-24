module V3Register (
    input wire clk,
    input wire enable,
    input wire d,
    output reg q
);

always @(posedge clk) begin : seq_p
    if (enable)
        q <= d;
end
endmodule
