module SvComb #(
    parameter int WIDTH = 8,
    localparam int LAST = WIDTH - 1
) (
    input  logic [LAST:0] a,
    input  logic [LAST:0] b,
    input  logic            sel,
    input  logic [1:0]      opcode,
    output logic [LAST:0]   y,
    output wire             parity
);
    assign parity = ^a;

    always_comb begin : comb_p
        if (sel) begin
            case (opcode)
                2'b00: y = a & b;
                2'b01: y = a | b;
                default: y = a ^ b;
            endcase
        end else begin
            y = b;
        end
    end
endmodule
