module SvNoReset (
    input wire clk,
    input wire d,
    output reg q
);

always @(posedge clk) begin : state_ff
    q <= d;
end

endmodule
