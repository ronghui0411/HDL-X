module SvAsyncHighReg #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             en,
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);
    always_ff @(posedge clk or posedge rst) begin : async_high_ff
        if (rst)
            q <= '0;
        else if (en)
            q <= d;
    end
endmodule

module SvSyncLowReg #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             en,
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);
    always_ff @(posedge clk) begin : sync_low_ff
        if (!rst_n)
            q <= '0;
        else if (en)
            q <= d;
    end
endmodule
