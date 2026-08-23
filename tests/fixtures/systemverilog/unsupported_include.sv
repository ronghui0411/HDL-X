`include "included_helper.svh"

module UnsupportedInclude(input logic a, output logic y);
    IncludedHelper helper(.a(a), .y(y));
endmodule
