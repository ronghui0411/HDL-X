/// SystemVerilog module comment
module SvComments (
    input  logic a,
    input  logic b,
    output logic y
);
    // This internal comment cannot yet be associated safely.
    assign y = a & b;
endmodule
