module UnsupportedClocking(input logic clk);
    clocking cb @(posedge clk);
    endclocking
endmodule
