module SvDeclarations #(
    parameter int WIDTH = 4
) (
    input  logic a,
    input  logic b,
    input  logic sel,
    input  logic signed [WIDTH-1:0] signed_a,
    input  wire  signed [WIDTH-1:0] signed_b,
    output wire                         y,
    output logic signed [WIDTH-1:0] signed_y
);
    logic selected;
    wire combined;
    reg signed [WIDTH-1:0] signed_sum;

    assign combined = a & b;
    always_comb begin
        selected = sel ? combined : a;
        signed_sum = signed_a + signed_b;
        signed_y = signed_sum;
    end
    assign y = selected;
endmodule
