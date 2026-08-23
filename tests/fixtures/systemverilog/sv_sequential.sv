module SvAsyncReg #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             en,
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);
    always_ff @(posedge clk or negedge rst_n) begin : async_ff
        if (!rst_n)
            q <= '0;
        else if (en)
            q <= d;
    end
endmodule

module SvSyncReg #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst,
    input  logic             en,
    input  logic [WIDTH-1:0] d,
    output logic [WIDTH-1:0] q
);
    always_ff @(negedge clk) begin : sync_ff
        if (rst)
            q <= '0;
        else if (en)
            q <= d;
    end
endmodule
