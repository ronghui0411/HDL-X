// commented module
module V3Comments (
  // input a docs
  input wire a, // input a trailing
  input wire b,
  output reg y
);
  // combinational process
  always @(*) begin
    // branch docs
    if (a) begin
      y = b; // true assignment
    end else begin
      // false assignment
      y = 1'b0;
    end
  end
endmodule
