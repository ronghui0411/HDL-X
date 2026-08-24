# HDL-X v0.3.0-rc1 Verilog-2001 → VHDL-2008 MVP

## 1. Stable baseline and compatibility contract

v0.3 starts from the published `v0.2.0` commit
`f283854d2d059e1bc54174d7f9509430c984bbe7`. The published tag, Release,
wheel, SBOM and golden files are immutable historical artifacts. The working
candidate uses display version `0.3.0-rc1` and PEP 440 version `0.3.0rc1`; it is
not a tag or GitHub Release.

The new path must preserve all of the following:

- VHDL → Verilog-2001 and SystemVerilog → Verilog-2001 output byte-for-byte;
- the public Canonical IR node classes, JSON fields and deprecated compatibility fields;
- `ConversionResult.design` as a Canonical `Design`;
- the existing `VerilogLowering`, `VerilogRenderIR`, renderer and generator facade;
- strict/best-effort policy: best-effort may omit only non-semantic trivia with a warning.

The first v0.3 slice does not require a Canonical IR schema extension. Target-only
decisions are carried by a separate VHDL render IR. If a later slice cannot remain
inside that contract, implementation must stop before changing the public schema.

## 2. Required architecture

```text
Verilog-2001 source
  → pyslang 11.0.0 SyntaxTree + Compilation
  → parser/slang private pure-Python Raw IR
  → VerilogAdapter
  → language-neutral Canonical RTL IR
  → VerilogToVhdl semantic boundary analysis
  → pipeline-owned VhdlLowering
  → VhdlRenderIR
  → VhdlRenderer + Jinja2 layout templates
  → VHDL-2008
  → real GHDL validation
```

pyslang objects may exist only inside `parser/slang`. Raw IR, Canonical IR,
semantic analysis, VHDL lowering and rendering must be recursively free of pyslang
types. Jinja2 receives already-lowered target structures and performs layout only.

## 3. Initial supported subset

- one source file containing one or more `module` declarations;
- ANSI Verilog-2001 ports and integral `parameter` declarations with defaults;
- `wire`, `reg`, `integer`, scalar and one-dimensional packed vectors;
- signed and unsigned packed vectors when operand signedness and sizing are provable;
- continuous `assign` without delay or strength;
- combinational `always @*`, `always @(*)` and simple explicit sensitivity lists;
- edge-triggered `always` with one clock and an optional asynchronous reset event;
- common synchronous/asynchronous, active-high/active-low reset forms;
- combinational blocking assignment and sequential nonblocking assignment;
- `if`/`else`, exact `case`/`default` and simple nested blocks;
- integral literals, index, slice, concatenation, ternary and the documented basic
  arithmetic, logical, comparison and shift operators;
- named or positional parameter and port connections;
- direct entity instantiation for modules available in the same design;
- simple static `for`/`if` generate after the base process/instance slice is green;
- Verilog comments that can be associated safely by parser-derived source spans.

The target uses `std_logic`, `unsigned`, `signed`, `integer`, `ieee.std_logic_1164`
and `ieee.numeric_std`. Verilog packed range direction is retained verbatim as VHDL
`to` or `downto`.

## 4. Assignment and process semantics

Combinational Verilog blocking assignments cannot be rendered as ordinary VHDL
signal assignments without changing read-after-write behavior. VHDL lowering must:

1. create one process-local persistent variable for every procedurally assigned
   signal in a combinational process;
2. rewrite reads and writes of those objects to the local variables;
3. use VHDL variable assignment (`:=`) inside the translated statements;
4. copy each local variable to its corresponding signal with `<=` at process end.

The persistent variable also preserves intentional latch state when a source branch
does not assign the object. Sequential nonblocking assignments map directly to VHDL
signal assignments inside the detected clock/reset process. Sequential blocking,
combinational nonblocking, or mixed assignment classes are rejected rather than
guessed.

## 5. Conservative semantic boundaries

The following structures are unsafe in the initial MVP and must fail in strict and
best-effort modes with an `HDLX-V2V-*` diagnostic:

- non-ANSI ports, implicit nets or unsupported declaration dimensions;
- `initial`, `final`, delay/event/wait/testbench constructs, force/release and UDPs;
- functions/tasks, specify blocks, primitives, package/import and any include flow;
- multiple drivers, mixed continuous/procedural drivers and ambiguous process writes;
- tri-state/resolved-net behavior, drive strengths and charge/storage semantics;
- ordinary level-sensitive always blocks that cannot be proven combinational;
- mixed edge and level events, multiple clocks or ambiguous reset classification;
- sequential blocking or combinational nonblocking assignment;
- `casex`/`casez`, wildcard matching or target-dependent X optimism;
- mixed signed/unsigned sizing, implicit truncation/width-mismatched arithmetic and
  unsupported literal sizing;
- cross-file compilation units or unresolved external interfaces;
- unlabeled/case generate, if-generate with independently labeled else hierarchy,
  dynamic bounds or unsupported generate-local declarations.

Warnings are required for boundaries that preserve the declared synthesis structure
but not the complete language-level simulation model:

- `HDLX-V2V-TIME-ZERO`: VHDL sensitivity processes execute once at time zero;
- `HDLX-V2V-EDGE-META`: Verilog and VHDL edge functions differ for X/Z transitions;
- `HDLX-V2V-INITIAL-STATE`: Verilog `X` and VHDL `U` initial states are not identical;
- `HDLX-V2V-META-VALUE`: explicit X is representable but propagation is not declared
  cycle-for-cycle equivalent;
- `HDLX-V2V-UNSIZED-SIZING`: unsized integer rules and VHDL overload/target sizing
  are not declared generally equivalent.

## 6. Naming, hierarchy and comments

Verilog identifiers are case-sensitive; VHDL basic identifiers are not. VHDL
lowering therefore owns a deterministic, case-insensitive target allocator. It must
handle VHDL reserved words, illegal underscore placement, illegal characters and
collisions such as `Data` versus `data` without changing Canonical source names.
Named instance formals are rewritten using the referenced unit's target interface.

Source locations exposed by the new path remain 1-based. Slang source ranges are
copied into private Raw spans before parser objects are released. Comments are mapped
only to nodes with a safe source-span association; strict mode fails on the remainder,
while best-effort reports exactly which comments were omitted.

## 7. Verification gates

The implementation is accepted only when all of these are true:

- real pyslang parses every positive and negative Verilog fixture;
- generated VHDL is analyzed by real GHDL/libghdl in local integration tests;
- CI with standalone GHDL and Icarus runs compile/differential scenarios with zero
  test skips;
- combination, register, reset, signed arithmetic, parameter and instance scenarios
  have end-to-end coverage;
- v0.2 VHDL and SystemVerilog golden files have zero diff;
- full pytest, Ruff, compileall, pip check and isolated wheelhouse smoke pass;
- version metadata, SBOM and v0.3 release checklist remain synchronized.

The committed CI contract requires the seven Verilog→VHDL differential scenarios
to report `7/7 passed, 0 skipped`. On the current Windows host, the generated VHDL
DUT + testbench pairs pass pyGHDL 6.0.0 analysis 7/7 and the original Verilog DUT +
testbench pairs pass pyslang 11.0.0 semantic compilation 7/7; standalone GHDL,
Icarus and VVP are absent, so no local trace-equivalence pass is claimed. Remote
CI evidence remains mandatory before RC acceptance.

No v0.3 tag or GitHub Release may be created without a separate owner approval.
