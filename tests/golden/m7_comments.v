/// Commented datapath
module M7Comments (
    // source port
    input wire source,
    // sampled input
    output wire assigned_result,
    output reg process_result
);

// intermediate signal
wire internal_value;

// internal connection
assign internal_value = source;

// concurrent output
assign assigned_result = internal_value;

// combinational output process
always @(source) begin : comb_logic
    // process assignment
    process_result = source;
end

endmodule
