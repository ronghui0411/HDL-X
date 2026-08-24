module V3CombCase (
    input wire a,
    input wire b,
    input wire enable,
    input wire [1:0] opcode,
    output reg y
);

always @(*) begin : comb_p
    if (enable) begin
        case (opcode)
            2'b00: y = a;
            2'b01: y = b;
            default: y = a ^ b;
        endcase
    end else begin
        y = b;
    end
end
endmodule
