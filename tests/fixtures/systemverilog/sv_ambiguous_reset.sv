module SvAmbiguousReset (
    input  logic clk,
    input  logic clear_n,
    input  logic d,
    output logic q
);
    always_ff @(posedge clk) begin
        if (!clear_n)
            q <= 1'b0;
        else
            q <= d;
    end
endmodule
