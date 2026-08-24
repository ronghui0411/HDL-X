module V3IntegerCounter (
  input wire clk,
  input wire rst,
  output integer count
);
  always @(posedge clk) begin
    if (rst)
      count <= 0;
    else
      count <= count + 1;
  end
endmodule
