# HDL-X MVP Execution Plan

## 1. Objective

Continuously implement the first usable HDL-X MVP.

The primary development path is:

```text
VHDL synthesizable RTL subset
        ↓
GHDL-based frontend
        ↓
HDL-X canonical RTL IR
        ↓
semantic lowering
        ↓
Verilog-2001 generator
        ↓
readable synthesizable Verilog
```

The implementation must follow all rules in:

```text
AGENTS.md
```

This plan is designed for unattended execution.

Do not wait for user confirmation between milestones.

---

# 2. Final MVP Target

By the end of this plan, HDL-X should support a meaningful VHDL → Verilog-2001 subset including:

- entity
- architecture
- ports
- std_logic
- std_logic_vector
- basic signed/unsigned awareness
- concurrent assignments
- conditional concurrent assignments
- combinational processes
- if/else
- basic case statements where practical
- sequential processes
- rising_edge
- falling_edge
- synchronous reset
- asynchronous reset
- generic → parameter
- generic expressions needed for vector widths
- entity/component instances
- generic map
- port map
- for-generate
- if-generate
- source diagnostics
- source spans where available
- comment preservation for supported common cases
- strict / best-effort infrastructure
- CLI
- validation infrastructure

This plan does **not** attempt full VHDL language support.

---

# 3. Explicitly Out of Scope

Do not automatically begin implementing:

```text
Verilog → VHDL
SystemVerilog → Verilog
VHDL → SystemVerilog
SystemVerilog → VHDL
```

Do not implement advanced testbench features.

Do not implement synthesis-based translation.

Do not flatten design hierarchy.

Do not attempt complete VHDL package semantics.

Do not expand the MVP into a complete HDL compiler.

---

# 4. Execution Mode

This run is an unattended continuous execution.

After each milestone:

1. run the milestone validation
2. inspect failures
3. fix regressions caused by the milestone
4. rerun validation
5. update progress records
6. continue automatically when acceptance criteria are satisfied

Do not ask:

```text
是否继续？
Should I continue?
Proceed to the next milestone?
```

unless a Hard Stop Condition is reached.

Ordinary implementation decisions should be resolved autonomously.

---

# 5. Development Memory

Create and maintain:

```text
DEVELOPMENT_LOG.md
```

if it does not already exist.

After every milestone, append or update a concise section containing:

```text
Milestone
Status
Implemented
Files changed
Tests executed
Validation results
Important design decisions
Known limitations
Technical debt
```

Do not claim validation that was not actually executed.

---

# 6. Progress Tracking

Maintain this section as execution proceeds.

Allowed states:

```text
[ ] not started
[~] in progress
[x] completed
[!] blocked
```

Initial state:

```text
[x] Milestone 0 — Repository and Environment Reconnaissance
[x] Milestone 1 — Architecture Foundation
[x] Milestone 2 — Minimal VHDL → Verilog Vertical Slice
[x] Milestone 3 — Combinational RTL
[x] Milestone 4 — Sequential RTL
[x] Milestone 5 — Generic / Parameter Support
[x] Milestone 6 — Hierarchical Instance Support
[x] Milestone 7 — Generate and Comment Preservation
[x] Milestone 8 — MVP Integration, Regression and Review
```

Update this section as milestones are completed.

Do not rewrite completed milestones merely to make the progress list look cleaner.

---

# 7. General Decision Policy

When encountering a normal engineering choice:

1. inspect existing implementation
2. inspect relevant installed APIs
3. compare plausible solutions
4. choose the solution that best preserves RTL semantics and architecture
5. document non-trivial decisions in `DEVELOPMENT_LOG.md`
6. continue

Priority:

```text
semantic correctness
>
synthesizability
>
architectural integrity
>
readability
>
feature breadth
```

Do not stop for minor naming, formatting, or internal API choices.

---

# 8. Architecture Repair Policy

If a milestone reveals an architecture defect:

Example:

```text
VectorRange loses ascending/descending direction.
```

or:

```text
Process IR cannot represent asynchronous reset semantics.
```

then:

1. identify root cause
2. repair the correct abstraction layer
3. update dependent code
4. add regression tests
5. rerun previously passing tests
6. document the architectural change
7. continue

Do not preserve a broken abstraction merely because it was created in an earlier milestone.

Do not patch architectural defects only inside a target generator.

---

# 9. Test Failure Policy

When a test fails:

```text
failure
  ↓
root-cause analysis
  ↓
targeted fix
  ↓
rerun relevant tests
  ↓
regression tests
  ↓
continue
```

Forbidden ways to advance:

- deleting a valid test
- weakening an assertion without semantic justification
- marking a valid test skipped merely because implementation is difficult
- silently removing a feature from the milestone
- catching and ignoring semantic errors
- replacing real parsing with hard-coded fixture-specific behavior

Environmental test skips are acceptable only when an external optional validator is genuinely unavailable.

Such skips must be clearly reported.

---

# 10. Hard Stop Conditions

Only stop the entire unattended run for one of the following.

## Hard Stop A — Required external frontend unavailable

The VHDL vertical slice requires a usable GHDL-based frontend.

If:

- GHDL is unavailable,
- the required backend cannot be installed or used within existing permissions,
- and there is no compliant GHDL-based alternative already available,

then stop.

Do not replace GHDL with a homemade VHDL parser.

Before stopping, document:

- detected environment
- commands checked
- installation/API issue
- attempted safe alternatives

---

## Hard Stop B — External API cannot be reliably determined

If a critical external API is required and:

- installed package/executable inspection is insufficient,
- local source/docs are insufficient,
- available official documentation cannot resolve it,

and guessing the API would likely create invalid implementation:

stop.

Do not invent APIs.

---

## Hard Stop C — Irreducible RTL semantic ambiguity

If continuing requires choosing between interpretations that produce different hardware behavior and there is no conservative interpretation supported by the source structure:

stop.

Document:

- source example
- possible interpretations
- why semantics differ
- recommended user decision

---

## Hard Stop D — Unsafe repository state

Stop if continuing would require:

- deleting unrelated user data
- destructive Git operations
- overwriting substantial unrelated work
- modifying files outside the permitted workspace without authorization

---

## Hard Stop E — Persistent foundational failure

If a foundational issue remains unresolved after multiple reasonable approaches and prevents all subsequent meaningful milestones:

stop.

Document:

- root cause hypothesis
- approaches attempted
- failing tests
- current repository state
- next recommended investigation

Do not spend the remaining run repeatedly applying equivalent patches.

---

# 11. Optional Tool Policy

The absence of an **optional validator** is not a hard stop.

Examples:

```text
slang validator unavailable
Yosys unavailable
```

In that case:

- continue if core implementation can still be tested
- mark that validation as unavailable
- make `hdl-x doctor` report it correctly
- document it in `DEVELOPMENT_LOG.md`

GHDL is different for the active VHDL frontend path because it is part of the required architecture.

---

# 12. Git Policy

Do not push to remote repositories.

Do not perform destructive Git operations.

If the repository is already a Git repository and:

- the working tree has no unrelated user changes,
- milestone changes are coherent,
- local checkpoint commits are safe,

Codex may create local milestone checkpoint commits.

Recommended style:

```text
milestone 1: establish canonical RTL IR
milestone 2: add minimal VHDL to Verilog path
```

If there are unrelated dirty changes, do not commit them.

Checkpoint commits are optional and must never block progress.

---

# Milestone 0 — Repository and Environment Reconnaissance

## Goal

Understand the real starting state before writing implementation code.

---

## Tasks

Inspect:

- repository tree
- existing `AGENTS.md`
- existing `PLANS.md`
- existing source files
- existing tests
- Git status if Git exists
- Python version
- installed package environment

Check availability of:

```text
Python
pydantic
jinja2
typer
pytest
GHDL
pyslang/slang
Yosys
```

Do not assume all are installed.

Determine actual tool versions where available.

---

## Dependencies

Create or update as appropriate:

```text
pyproject.toml
requirements.txt
```

Prefer `pyproject.toml` as the authoritative Python project definition.

`requirements.txt` may be retained for convenience if required by project goals.

Do not duplicate incompatible dependency constraints.

---

## Environment Report

Record in `DEVELOPMENT_LOG.md`:

```text
Python:
Pydantic:
Typer:
Jinja2:
pytest:
GHDL:
pyslang/slang:
Yosys:
OS:
```

Use actual observed values.

---

## Acceptance Criteria

Milestone 0 is complete when:

- repository state is understood
- available external tools are known
- Python project layout strategy is known
- no existing implementation has been blindly overwritten

Automatically continue to Milestone 1.

---

# Milestone 1 — Architecture Foundation

## Goal

Create a coherent compiler-style architecture without implementing the complete VHDL parser.

---

## Target Layout

Prefer approximately:

```text
hdl-x/
├── AGENTS.md
├── PLANS.md
├── DEVELOPMENT_LOG.md
├── README.md
├── pyproject.toml
├── requirements.txt
│
├── src/
│   └── hdl_x/
│       ├── __init__.py
│       │
│       ├── cli/
│       │   ├── __init__.py
│       │   └── main.py
│       │
│       ├── frontend/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── vhdl.py
│       │
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── vhdl_adapter.py
│       │   └── ghdl/
│       │       ├── __init__.py
│       │       ├── base.py
│       │       ├── xml_backend.py
│       │       └── pyghdl_backend.py
│       │
│       ├── ir/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── types.py
│       │   ├── expressions.py
│       │   ├── statements.py
│       │   ├── module.py
│       │   └── design.py
│       │
│       ├── transformer/
│       │   ├── __init__.py
│       │   ├── semantic_lowering.py
│       │   ├── type_lowering.py
│       │   ├── identifier_resolver.py
│       │   └── name_transformer.py
│       │
│       ├── generator/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── verilog.py
│       │
│       ├── templates/
│       │   └── verilog/
│       │
│       ├── diagnostics/
│       │   ├── __init__.py
│       │   ├── diagnostic.py
│       │   └── errors.py
│       │
│       ├── validator/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── slang.py
│       │   ├── ghdl.py
│       │   └── yosys.py
│       │
│       └── utils/
│           ├── subprocess.py
│           └── paths.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── golden/
    └── fixtures/
```

This structure may be adjusted if a clearly better separation emerges.

Document significant structural deviations.

---

## Source Provenance Models

Implement concepts equivalent to:

```text
SourceLocation
SourceSpan
Comment
```

Useful comment fields include:

```text
text
kind
placement
source_span
```

Support concepts such as:

```text
LINE
BLOCK
DOC
LEADING
TRAILING
```

Do not over-engineer comment placement before the frontend exists.

---

## IR Base

Create:

```text
IRNode
```

using Pydantic v2.

Relevant nodes should support:

```text
source_span
leading_comments
trailing_comments
```

---

## Type System

Implement at least:

```text
RTLType
ScalarType
VectorType
IntegerType
BooleanType
```

Vector/range representation must preserve:

- bounds
- ascending/descending direction
- width derivation where possible
- signedness
- four-state information where relevant

Test:

```text
7 downto 0
0 to 7
```

as distinct range orientations.

---

## Expressions

Implement at least:

```text
Identifier
Literal
UnaryExpr
BinaryExpr
TernaryExpr
Concatenation
Index
Slice
FunctionCall
```

Expression operators should use canonical semantics or controlled enums where appropriate rather than raw source tokens everywhere.

---

## Statements

Implement at least:

```text
ContinuousAssignment
ProceduralAssignment
IfStatement
CaseStatement
ForStatement
BlockStatement
NullStatement
```

Procedural assignment representation must support the semantic distinction required to later generate blocking/non-blocking assignments correctly.

---

## Processes

Implement representations capable of expressing:

```text
CombinationalProcess
SequentialProcess
```

Sequential process representation must have an extensible way to represent:

- clock signal
- edge
- reset signal
- reset polarity
- synchronous/asynchronous reset

Avoid VHDL-specific syntax in canonical models.

---

## Modules

Implement concepts equivalent to:

```text
Design
Module
Parameter
Port
Signal
Variable
Instance
```

Instance must support:

```text
referenced design unit
instance name
parameter/generic bindings
port bindings
```

---

## Generate

Implement:

```text
ForGenerate
IfGenerate
```

with hierarchy-preserving representation.

---

## Interfaces

Create clean abstractions for:

```text
Frontend
ParserAdapter
GhdlFrontendBackend
SemanticLowering
Generator
Validator
IdentifierResolver
```

Only define APIs needed by foreseeable MVP behavior.

Avoid speculative complex frameworks.

---

## Diagnostics

Implement structured diagnostics and errors.

At least:

```text
Diagnostic
DiagnosticSeverity
FrontendError
UnsupportedConstructError
SemanticError
GenerationError
ValidationError
```

Support file/line/column/source span when known.

---

## Architecture Self-Review

Before completing Milestone 1, explicitly review:

1. Is canonical IR language-neutral?
2. Are GHDL/slang types absent from canonical IR?
3. Can vector ranges preserve ascending vs descending?
4. Can processes represent combinational and sequential semantics?
5. Can reset semantics be represented without VHDL-specific syntax?
6. Can assignment semantics later map correctly to Verilog?
7. Can Instance represent named/positional associations as needed?
8. Can Generate preserve hierarchy?
9. Is Generator independent from frontend?
10. Is semantic analysis absent from Jinja templates?

Repair Critical architecture issues before proceeding.

---

## Tests

Create unit tests covering at least:

- model construction
- invalid model validation
- vector range direction
- process representation
- assignment representation
- instance representation
- generate representation
- diagnostics/source spans

---

## Acceptance Criteria

Milestone 1 is complete when:

- project package imports successfully
- canonical IR models instantiate correctly
- architecture self-review finds no unresolved Critical defect
- relevant unit tests pass
- no frontend-specific node types leak into generator-facing canonical IR

Automatically continue to Milestone 2.

---

# Milestone 2 — Minimal VHDL → Verilog Vertical Slice

## Goal

Implement the first real end-to-end conversion.

---

## Supported Source Subset

Support:

```text
entity
architecture
port
std_logic
std_logic_vector
basic concurrent signal assignment
basic logic expressions
```

Primary example:

```vhdl
library ieee;
use ieee.std_logic_1164.all;

entity and_gate is
    port (
        a : in  std_logic;
        b : in  std_logic;
        y : out std_logic
    );
end entity;

architecture rtl of and_gate is
begin
    y <= a and b;
end architecture;
```

Expected style:

```verilog
module and_gate (
    input  wire a,
    input  wire b,
    output wire y
);

assign y = a & b;

endmodule
```

Exact whitespace may differ if internally consistent.

---

## GHDL Backend

Implement a real GHDL-based frontend.

Do not write a standalone VHDL parser.

Inspect the installed GHDL version.

Choose the best usable backend supported by the real environment.

Possible architecture:

```text
GhdlFrontendBackend
├── GhdlXmlBackend
└── PyGhdlBackend
```

It is acceptable to initially implement only one concrete backend while preserving the abstraction.

Do not invent pyGHDL/libghdl APIs.

---

## VHDL AST Adapter

Convert frontend representation into HDL-X IR.

At minimum map:

```text
entity
architecture
port
std_logic
std_logic_vector
concurrent assignment
Identifier
Literal
UnaryExpr
BinaryExpr
```

Map VHDL logical operators semantically.

Examples:

```text
and
or
xor
not
```

must become canonical operators before Verilog rendering.

---

## Verilog Generator

Implement a Verilog-2001 generator using Jinja2.

Templates should handle presentation.

Python generator code should traverse canonical IR and prepare render models as necessary.

Do not embed semantic inference into templates.

---

## CLI

Implement at least:

```bash
hdl-x convert input.vhd --from vhdl --to verilog -o output.v
```

Provide useful failure messages.

---

## Doctor Command

Begin implementation of:

```bash
hdl-x doctor
```

At minimum report:

- Python
- GHDL
- slang/pyslang
- Yosys

availability.

Do not fail doctor merely because optional validators are absent.

---

## Tests

At least:

```text
simple_and
simple_or
simple_xor
simple_not
vector_assignment
simple_expression
```

Include:

- parser/adapter IR tests
- generator unit tests
- golden output tests
- end-to-end conversion test

Where GHDL exists, the tests must exercise the real frontend rather than only mocks.

---

## Validation

If slang is available:

validate generated Verilog.

If Yosys is available:

run a basic synthesis smoke test.

Do not make optional validators hard requirements for this milestone.

---

## Acceptance Criteria

A real `.vhd` file from the declared subset must successfully travel through:

```text
VHDL
↓
GHDL frontend
↓
HDL-X IR
↓
semantic lowering
↓
Jinja2 Verilog generator
↓
valid readable .v
```

Relevant tests must pass.

Automatically continue to Milestone 3.

---

# Milestone 3 — Combinational RTL

## Goal

Support common combinational RTL structures.

---

## Concurrent Conditional Assignment

Support constructs equivalent to:

```vhdl
y <= a when sel = '1' else b;
```

Prefer readable expression-oriented output:

```verilog
assign y = sel ? a : b;
```

when semantics allow.

---

## Combinational Process

Support common sensitivity-list combinational processes such as:

```vhdl
process(a, b, sel)
begin
    if sel = '1' then
        y <= a;
    else
        y <= b;
    end if;
end process;
```

Expected form:

```verilog
always @(*) begin
    if (sel)
        y = a;
    else
        y = b;
end
```

---

## Required Semantics

Implement:

- process classification
- IfStatement
- nested if/else
- procedural combinational assignment
- basic case statement if feasible within the existing frontend structure
- output wire/reg lowering
- basic driver awareness required for Verilog-2001 declarations

Combinational procedural assignments must use:

```text
=
```

not non-blocking assignments.

---

## Safety

Do not generate incomplete combinational assignments that accidentally infer latches unless the VHDL source itself has equivalent latch semantics.

If the source process is incomplete and therefore latch-like:

preserve the semantics rather than silently “fixing” the source design.

---

## Tests

At least:

```text
if_else_mux
nested_if
conditional_assignment
vector_combinational_process
output_reg_inference
case_mux if implemented
intentional_latch_behavior if frontend allows
```

Add regression tests for Milestone 2.

---

## Acceptance Criteria

- supported combinational processes convert correctly
- declaration lowering produces legal Verilog-2001
- procedural combinational assignments use blocking assignments
- previous tests still pass
- generated Verilog validates when validator is available

Automatically continue to Milestone 4.

---

# Milestone 4 — Sequential RTL

## Goal

Support common clocked RTL.

---

## Basic Rising Edge

Support:

```vhdl
process(clk)
begin
    if rising_edge(clk) then
        q <= d;
    end if;
end process;
```

Expected semantic output:

```verilog
always @(posedge clk) begin
    q <= d;
end
```

---

## Falling Edge

Support:

```text
falling_edge(clk)
```

mapping to:

```text
negedge clk
```

---

## Resets

Support common:

```text
synchronous active-high reset
synchronous active-low reset
asynchronous active-high reset
asynchronous active-low reset
```

Determine reset behavior from structured process semantics and sensitivity/conditions.

Example:

```vhdl
process(clk, rst_n)
begin
    if rst_n = '0' then
        q <= '0';
    elsif rising_edge(clk) then
        q <= d;
    end if;
end process;
```

should semantically map to:

```verilog
always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
        q <= 1'b0;
    else
        q <= d;
end
```

---

## Sequential Assignment

Sequential procedural state assignments must use:

```text
<=
```

in generated Verilog.

Do not confuse VHDL signal assignment syntax with combinational/sequential Verilog operator choice.

---

## Tests

At least:

```text
dff_posedge
dff_negedge
counter
sync_reset_high
sync_reset_low
async_reset_high
async_reset_low
multi_register_process
```

Include regression tests for combinational output declaration behavior.

---

## Acceptance Criteria

- edge semantics are correct
- reset sensitivity is correct
- sequential assignments use non-blocking assignments
- supported designs validate
- earlier milestone tests still pass

Automatically continue to Milestone 5.

---

# Milestone 5 — Generic / Parameter Support

## Goal

Support parameterized RTL.

---

## Generic Declaration

Support common integer/natural-like width generics where practical.

Example:

```vhdl
generic (
    WIDTH : integer := 8
);
```

Expected target concept:

```verilog
parameter WIDTH = 8
```

---

## Parameter Expressions

Support expressions needed for common widths.

Example:

```vhdl
std_logic_vector(WIDTH-1 downto 0)
```

must preserve the parameterized range.

Do not eagerly evaluate expressions that must remain symbolic in generated Verilog.

---

## Type/Range Semantics

Ensure symbolic bounds remain represented in IR.

Do not design `VectorType.width` so that vectors require an immediately known integer width.

Represent symbolic ranges where needed.

---

## Tests

At least:

```text
generic_width
generic_default
parameterized_vector
parameterized_counter
generic_expression
```

---

## Acceptance Criteria

A common parameterized VHDL module converts to readable Verilog parameters without flattening or hard-coding the default value into all ranges.

Earlier tests continue passing.

Automatically continue to Milestone 6.

---

# Milestone 6 — Hierarchical Instance Support

## Goal

Preserve design hierarchy and module instances.

---

## Supported Concepts

Implement:

- entity/component instantiation as supported by frontend
- instance name
- port map
- generic map
- named association
- positional association only if it can be mapped safely with available semantic information

Prefer named Verilog port connections in generated code when semantic information allows.

---

## Example Target Style

```verilog
submodule #(
    .WIDTH(WIDTH)
) u_submodule (
    .clk  (clk),
    .rst_n(rst_n),
    .data (data)
);
```

Exact alignment is a formatting decision.

Semantics are primary.

---

## Hierarchy

Do not flatten:

```text
top
├── u_submodule_0
└── u_submodule_1
```

into duplicated internal logic.

Maintain referenced design-unit names and instance names.

---

## Identifier Resolution

Strengthen IdentifierResolver for:

- target keywords
- case collisions
- generated name collisions
- deterministic escaping/renaming

Default name style remains:

```text
preserve
```

---

## Tests

At least:

```text
simple_instance
two_instances
named_port_map
generic_map
parameterized_instance
identifier_collision
reserved_keyword_collision
```

---

## Acceptance Criteria

- hierarchy remains explicit
- instance names are preserved when legal
- generic/parameter overrides are preserved
- port relationships are correct
- previous tests continue passing

Automatically continue to Milestone 7.

---

# Milestone 7 — Generate and Comment Preservation

## Goal

Add common structural generate constructs and strengthen source preservation.

---

## For Generate

Support common VHDL:

```text
for-generate
```

mapping to Verilog-2001 generate structures.

Prefer preserving generate hierarchy instead of unrolling.

---

## If Generate

Support:

```text
if-generate
```

for parameter/generic-controlled elaboration where supported by Verilog-2001 semantics.

---

## Generate Naming

Preserve source generate labels where legal.

If generated names are required:

- deterministic
- readable
- collision-safe

Do not create unstable `_GEN_xxx` naming unless unavoidable.

---

## Comments

Implement or strengthen comment extraction and mapping.

Target common cases:

- comment before entity/module
- comment before port/signal declaration
- comment before concurrent assignment
- comment before process
- comment inside simple process blocks where practical

Use:

- source location
- frontend token/trivia support
- lightweight source comment scanning

as needed.

Do not build a second VHDL parser.

---

## Tests

At least:

```text
for_generate
if_generate
generated_instance
module_comment
port_comment
assignment_comment
process_comment
comment_regression
```

Golden tests should inspect reasonable comment placement.

Exact whitespace reproduction is not required.

---

## Acceptance Criteria

- generate hierarchy is preserved
- supported generate structures produce valid Verilog
- common comments survive translation in readable locations
- previous tests continue passing

Automatically continue to Milestone 8.

---

# Milestone 8 — MVP Integration, Regression and Review

## Goal

Stabilize the MVP instead of adding another large feature.

No new major translation path should be introduced.

---

# 8.1 Full Test Run

Run all project tests that can actually execute.

Prefer:

```text
unit
integration
golden
end-to-end
```

Record exact commands and results.

---

# 8.2 Python Quality

Run appropriate available checks.

At minimum:

- package import
- Python syntax/compile validation
- pytest

If type checking or linting has been configured in the project, run it.

Do not add large tooling stacks solely to satisfy this milestone.

---

# 8.3 GHDL Validation

Run representative supported VHDL inputs through the actual GHDL frontend.

Confirm that test fixtures are not accidentally bypassing the real parser.

---

# 8.4 Generated Verilog Validation

If slang is available:

validate representative and/or all suitable generated Verilog fixtures.

If Yosys is available:

run synthesis smoke tests on representative outputs.

Recommended conceptual Yosys flow:

```text
read_verilog
hierarchy
proc
check
```

Use commands appropriate to the actual installed version.

---

# 8.5 Semantic Review

Explicitly audit:

```text
blocking vs non-blocking
continuous vs procedural assignment
combinational process classification
sequential process classification
clock edge
sync reset
async reset
active-high reset
active-low reset
vector range direction
symbolic range
signedness
generic/parameter propagation
instance connectivity
generate hierarchy
```

Any discovered semantic bug should receive a regression test.

---

# 8.6 Architecture Review

Inspect for:

- GHDL types leaking into canonical IR
- frontend code leaking into generator
- target-language logic inside parser
- excessive semantic logic inside Jinja2
- duplicated lowering rules
- generator special cases masking IR defects
- circular dependencies
- overly broad modules
- unnecessary abstraction

Fix Critical and clear Major issues that threaten correctness or maintainability.

Do not perform aesthetic large-scale rewrites.

---

# 8.7 Generated HDL Readability Review

Inspect representative golden outputs as if reviewing human RTL.

Check:

- module declaration readability
- port formatting
- declaration order
- whitespace
- indentation
- assign readability
- always block readability
- instance formatting
- parameter formatting
- generate formatting
- comment placement
- unnecessary temporaries
- unnecessary generated names

Improve formatting without altering RTL semantics.

---

# 8.8 Unsupported Syntax Review

Ensure unsupported constructs produce explicit diagnostics.

Do not allow:

```text
silent skip
silent semantic degradation
successful exit with materially incomplete RTL
```

Strengthen strict/best-effort behavior where possible.

---

# 8.9 CLI Review

Confirm:

```bash
hdl-x convert input.vhd --from vhdl --to verilog -o output.v
```

works for the supported subset.

Check:

```text
--strict
--best-effort
--name-style
--validate
--verbose
```

to the extent implemented by the MVP.

Run:

```text
hdl-x doctor
```

or its package-entry equivalent and verify clear environment reporting.

---

# 8.10 README

Update README to describe only functionality that actually exists.

Include:

- project purpose
- current supported conversion path
- supported MVP syntax
- unsupported syntax
- installation
- external dependencies
- basic CLI usage
- doctor command
- strict/best-effort modes
- test instructions
- architecture overview

Do not advertise unimplemented Verilog → VHDL or SystemVerilog conversion as working.

It may be listed as planned work.

---

# 8.11 Final DEVELOPMENT_LOG Summary

Add a final summary containing:

```text
MVP status
Completed milestones
Implemented syntax
Known unsupported syntax
Test commands
Test results
GHDL validation status
slang validation status
Yosys validation status
Known technical debt
Known semantic limitations
Recommended next phase
```

Use actual results.

---

# 8.12 Final Acceptance Criteria

The unattended MVP run is considered complete when:

1. Milestones 0–8 are marked completed.
2. The VHDL → Verilog pipeline works end-to-end for the declared MVP subset.
3. Core tests pass.
4. No known Critical semantic bug remains unresolved.
5. Unsupported constructs do not silently produce incorrect HDL.
6. Generated Verilog is readable and deterministic.
7. GHDL frontend integration is real rather than fixture-specific parsing.
8. Optional validators have either run successfully or are explicitly recorded as unavailable.
9. README reflects actual capabilities.
10. DEVELOPMENT_LOG accurately summarizes the run.

Once these conditions are met:

STOP.

Do not begin:

```text
Verilog → VHDL
SystemVerilog → Verilog
Phase 2
```

without a new user request.

---

# 13. Final Response Format

When the plan completes, report concisely:

```text
Overall status

Completed milestones

Implemented features

Tests:
- command
- result

Validation:
- GHDL
- slang
- Yosys

Major files added/changed

Known limitations

Technical debt

Recommended next step
```

Do not claim perfection.

Clearly distinguish:

```text
implemented
tested
validated
not tested
unavailable
known limitation
```

---

# 14. Core Reminder

HDL-X is successful only if:

```text
source RTL
    ↓
semantic understanding
    ↓
canonical RTL representation
    ↓
correct readable target RTL
```

The goal is not maximum syntax coverage.

The goal is a trustworthy, extensible translation architecture with a working VHDL → Verilog MVP.

---

# 15. v0.2 SystemVerilog → Verilog-2001 MVP

本节由项目所有者在 v0.1.1 发布后明确授权，覆盖前述“未经新请求不启动 SystemVerilog”
的历史停止条件。v0.1.1 仍是兼容基线；详细语义边界见
`V0_2_SYSTEMVERILOG_MVP.md`，发布门禁见 `V0_2_RELEASE_CHECKLIST.md`。

## 15.1 目标与不变量

实现真实 Slang 驱动的、单文件可综合 SystemVerilog 子集到 Verilog-2001 的端到端路径。
必须同时保持：

- 现有 VHDL → Verilog-2001 行为和已跟踪 golden 逐字不变；
- 公开 Python API、`ConversionResult.design` 节点类型和 Canonical JSON 结构不变；
- Slang 类型不越过 frontend 私有边界；
- pipeline 拥有 Verilog lowering，renderer 只渲染 target render IR；
- unsupported 或语义无法证明安全的输入结构化失败，不扩大 best-effort 的 RTL 省略范围。

## 15.2 实施切片

1. **设计与基线 — completed**
   - 冻结 `v0.1.1` / `7bf9785` 基线、前端选择、支持矩阵、API 兼容和停止条件。
2. **真实前端与 Raw IR — completed**
   - 精确固定可选 `pyslang==11.0.0`；实际调用 `SyntaxTree` + `Compilation`。
   - 在 `parser/slang` 内复制为纯 Python Raw IR，再由 `SystemVerilogAdapter` 规范化。
3. **Canonical 与目标 lowering — completed**
   - 复用现有语言无关节点，不增加 Canonical JSON 字段。
   - 大小写敏感名称策略、driver/storage 和 `=`/`<=` 目标操作符在 Verilog lowering 完成。
4. **支持面与结构化诊断 — completed**
   - 覆盖 module/ANSI ports、parameter/localparam、logic/wire/reg、packed vector、assign、
     always_comb/always_ff、if/case、edge/reset、实例连接和符号宽度。
   - 明确拒绝 interface/class/package/clocking、复杂类型、testbench-only 和不安全语义。
5. **验证基础设施 — completed locally, external execution pending**
   - 真实 `.sv` fixture 贯穿 Slang → Raw → Canonical → lowering → renderer → golden。
   - 新增两个 Verilog-2001 编译场景及两个组合/clock-reset-enable 差分场景。
   - 本地缺失 Icarus/VVP 时普通入口明确 skip；强制入口非零失败。
   - Ubuntu 24.04 CI 固定 actions、pyslang wheel URL/SHA-256，先要求完整 Slang frontend
     30 passed、0 skipped，再要求编译/差分 4 passed、0 skipped；workflow 未经实际远端
     成功运行前不得声称等价门禁通过。
6. **完整验收 — completed locally; external equivalence pending**
   - 真实 Slang integration 30/30、真实 GHDL integration 129/129，均零跳过。
   - 完整回归 311 passed、6 skipped；六项只因本机缺少 GHDL CLI/Icarus/VVP。
   - Ruff、compileall、`pip check`、`git diff --check`、VHDL golden 审计和 wheel 内容检查通过。
   - Vivado 2023.2 `xvlog/xelab/xsim` 补充验证通过：组合 32/32 和 clock/reset/enable
     时序 6/6 源/目标 traces 逐项一致。Icarus pytest 4/4 零跳过与远端 CI 仍是未来
     v0.2 发布门禁，不能用该补充结果改写其 skipped 状态。

## 15.3 依赖与发布策略

- `pyslang` 是 `systemverilog` optional extra，不进入核心安装路径，也不捆绑进 HDL-X wheel。
- v0.1.1 的 `SBOM.cdx.json` 是历史发布快照；v0.2 发布前必须按最终 wheelhouse 重建。
- v0.2 MVP 不扩展 GUI 或 PyInstaller EXE，不自动下载外部 simulator。
- 当前工作只生成可审查的未提交修改；没有项目所有者的新授权时，不 commit、push、tag
  或创建 GitHub Release。

## 15.4 关键风险

- `always_comb` 的 time-zero 调度不能由 Verilog `always @(*)` 完整表达。
- reset 分类需要受控语法形态与命名约定；未命中时只能保留普通 clocked if/else。
- SystemVerilog expression sizing、signedness、two-state 类型及 compilation-unit 规则比现有
  Canonical IR 更丰富；超出可证明子集必须拒绝。
- 本机无 Icarus/VVP 时无法提供真实差分通过证据；只能验证 skip/强制失败门禁正确。
- 删除 deprecated Canonical 字段不是本计划内容，必须另行版本化迁移。

# 16. v0.3 Verilog-2001 → VHDL-2008 MVP

本节由项目所有者在 `v0.2.0` 正式发布后授权，覆盖前述“不自动实现
Verilog → VHDL”的历史范围限制。详细契约见
`V0_3_VERILOG_TO_VHDL_MVP.md`。

## 16.1 不变量

- 以 `v0.2.0` / `f283854d2d059e1bc54174d7f9509430c984bbe7` 为不可变稳定基线；
- 不修改已发布 tag、Release、wheel、SBOM 或既有 golden；
- 不改变 v0.2.0 Canonical IR/JSON、公开 API 或既有两条转换输出；
- Slang 对象只存在于 `parser/slang`，VHDL target 决策只存在新的
  semantic boundary / `VhdlLowering` / `VhdlRenderIR`；
- unsafe 构造在 strict 和 best-effort 中都以 `HDLX-V2V-*` 失败。

## 16.2 实施切片

1. **基线与设计 — completed**
   - 已核对稳定提交、tag、Release、CI、工具链和本地回归；
   - 已冻结兼容契约、支持/拒绝矩阵和停止条件。
2. **真实 Verilog frontend 与最小 assign 竖向切片 — completed**
3. **blocking 组合过程、if/case 与 target-local variable — completed**
4. **posedge/negedge、同步/异步 reset 与 nonblocking 时序过程 — completed**
5. **signed/width、parameter、instance 和必要 generate — completed**
6. **注释/span、负面语义证据、GHDL/Icarus 差分和 CI 门禁 — completed**
7. **完整回归、wheel/SBOM/文档同步与 rc1 readiness — completed**
