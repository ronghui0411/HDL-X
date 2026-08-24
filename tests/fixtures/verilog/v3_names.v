module entity (
  input wire process,
  input wire Data,
  input wire data,
  output wire result
);
  assign result = process & Data & data;
endmodule
