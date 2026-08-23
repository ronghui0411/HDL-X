module SvNoReset (
    input  logic clk,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin : state_ff
        q <= d;
    end
endmodule
