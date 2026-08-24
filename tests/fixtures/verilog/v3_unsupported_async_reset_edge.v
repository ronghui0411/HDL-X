module V3UnsupportedAsyncResetEdge (
    input wire clk,
    input wire rst_n,
    input wire d,
    output reg q
);
always @(posedge clk or posedge rst_n) begin
    if (!rst_n)
        q <= 1'b0;
    else
        q <= d;
end
endmodule
