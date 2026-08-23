module SvAsyncHighReg #(
    parameter integer WIDTH = 8
) (
    input wire clk,
    input wire rst,
    input wire en,
    input wire [WIDTH - 1:0] d,
    output reg [WIDTH - 1:0] q
);

always @(posedge clk or posedge rst) begin : async_high_ff
    if (rst) begin
        q <= 0;
    end else begin
        if (en) begin
            q <= d;
        end
    end
end

endmodule

module SvSyncLowReg #(
    parameter integer WIDTH = 8
) (
    input wire clk,
    input wire rst_n,
    input wire en,
    input wire [WIDTH - 1:0] d,
    output reg [WIDTH - 1:0] q
);

always @(posedge clk) begin : sync_low_ff
    if (!rst_n) begin
        q <= 0;
    end else begin
        if (en) begin
            q <= d;
        end
    end
end

endmodule
