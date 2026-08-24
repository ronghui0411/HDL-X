module V3AsyncReset (
    input wire clk,
    input wire rst_n,
    input wire enable,
    input wire d,
    output reg q
);
always @(posedge clk or negedge rst_n) begin : async_p
    if (!rst_n)
        q <= 1'b0;
    else if (enable)
        q <= d;
end
endmodule

module V3SyncReset (
    input wire clk,
    input wire rst,
    input wire d,
    output reg q
);
always @(negedge clk) begin : sync_p
    if (rst)
        q <= 1'b0;
    else
        q <= d;
end
endmodule
