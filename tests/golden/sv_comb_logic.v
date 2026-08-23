module SvComb #(
    parameter integer WIDTH = 8
) (
    input wire [WIDTH - 1:0] a,
    input wire [WIDTH - 1:0] b,
    input wire sel,
    input wire [1:0] opcode,
    output reg [WIDTH - 1:0] y,
    output wire parity
);

assign parity = ^a;

always @(*) begin : comb_p
    if (sel) begin
        case (opcode)
            2'b00: begin
                y = a & b;
            end
            2'b01: begin
                y = a | b;
            end
            default: begin
                y = a ^ b;
            end
        endcase
    end else begin
        y = b;
    end
end

endmodule
