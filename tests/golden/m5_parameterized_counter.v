module M5ParameterizedCounter #(
    parameter integer WIDTH = 8
) (
    input wire clk,
    output reg [WIDTH - 1:0] count
);

always @(posedge clk) begin : counter_p
    count <= count + 1;
end

endmodule
