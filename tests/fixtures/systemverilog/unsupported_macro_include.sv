`include "included_width.svh"

module UnsupportedMacroInclude (
    input  logic [`HDL_X_INCLUDED_WIDTH-1:0] a,
    output logic [`HDL_X_INCLUDED_WIDTH-1:0] y
);
    assign y = a;
endmodule
