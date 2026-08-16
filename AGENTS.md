# HDL-X — AGENTS.md

## 1. Project Mission

HDL-X is an offline HDL source-to-source translation tool.

Its goal is to translate synthesizable RTL subsets between:

- VHDL
- Verilog
- SystemVerilog

while preserving, as far as reasonably possible:

- RTL semantics
- design hierarchy
- module/entity structure
- instance names
- signal relationships
- generate structure
- source comments
- human readability

HDL-X is **not** a synthesis-based netlist converter.

The generated HDL should resemble maintainable RTL written by an experienced digital IC engineer rather than generated gate-level or flattened code.

---

# 2. Priority Order

When requirements conflict, use the following priority:

1. RTL semantic correctness
2. Synthesizability
3. Source hierarchy preservation
4. Structural readability
5. Comment preservation
6. Formatting aesthetics

Never sacrifice RTL correctness merely to generate prettier code.

Never silently generate HDL whose semantics are uncertain.

---

# 3. Supported Development Scope

The current MVP focuses on:

1. VHDL synthesizable subset → Verilog-2001

Architecture should remain extensible for:

2. Verilog-2001 → VHDL-93
3. SystemVerilog synthesizable subset → Verilog-2001
4. Future Verilog/VHDL → SystemVerilog
5. Future SystemVerilog ↔ VHDL

Do not implement Phase 2 functionality unless the active execution plan explicitly requests it.

Do not expand scope simply because adjacent functionality appears easy.

---

# 4. Mandatory Architecture

The main translation pipeline must follow this conceptual structure:

```text
HDL Source
    ↓
Frontend
    ↓
Frontend AST / CST
    ↓
AST Adapter
    ↓
Raw IR
    ↓
Semantic Normalization / Lowering
    ↓
Canonical RTL IR
    ↓
Target Generator
    ↓
Jinja2 Templates
    ↓
Generated HDL
    ↓
Validator
```

Frontend-specific representations must not leak into later stages.

In particular:

- GHDL node types must not appear in the canonical IR.
- slang/pyslang node types must not appear in the canonical IR.
- Generators must not depend directly on slang, pyslang, GHDL, pyGHDL, or libghdl.
- Templates must not perform semantic analysis.

---

# 5. Parser Policy

Do not implement a complete HDL grammar parser from scratch.

## Verilog / SystemVerilog

Use the slang ecosystem.

Preferred interface:

- pyslang

Allowed fallback:

- slang command-line serialization or other officially supported slang interfaces

Use the appropriate source representation for the task.

Semantic AST is suitable for:

- symbol resolution
- type information
- constant evaluation
- elaborated semantic structure

CST/token/trivia/source information may be needed for:

- source locations
- comments
- whitespace-sensitive source mapping

Do not assume one representation automatically contains all information required for comment preservation.

---

## VHDL

Use the GHDL ecosystem.

The VHDL frontend must be isolated behind a backend abstraction.

Conceptually support implementations such as:

```text
GhdlFrontendBackend
├── GhdlXmlBackend
└── PyGhdlBackend
```

All GHDL-specific logic should remain under an implementation-specific frontend/parser layer.

Do not hard-code an API from memory.

When working with:

- GHDL
- pyGHDL
- libghdl

inspect the installed version and available API before implementing integration code.

If the actual API differs from expectations, adapt to the actual environment rather than inventing methods.

---

# 6. Canonical RTL IR

The canonical IR must be language-neutral.

Use:

- Python 3.10+
- Pydantic v2 `BaseModel`

Do not maintain duplicate dataclass and Pydantic versions of the same IR.

Core nodes should derive from a common base such as:

```python
IRNode
```

IR nodes should support source provenance where relevant:

```python
source_span
leading_comments
trailing_comments
```

The canonical IR should use semantic concepts rather than source-language syntax names.

Good:

```text
CombinationalProcess
SequentialProcess
ContinuousAssignment
ProceduralAssignment
```

Avoid canonical IR nodes such as:

```text
VhdlProcess
VerilogAlways
SystemVerilogAlwaysComb
```

Source-language-specific temporary structures may exist in frontend adapters, but they must be lowered before reaching canonical IR consumers.

---

# 7. Minimum IR Concepts

The architecture should be able to represent at least:

```text
Design
Module
Parameter
Port
Signal
Variable
Instance

SourceLocation
SourceSpan
Comment
```

RTL types:

```text
RTLType
ScalarType
VectorType
IntegerType
BooleanType
```

Expressions:

```text
Expression
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

Statements:

```text
Statement
ContinuousAssignment
ProceduralAssignment
IfStatement
CaseStatement
ForStatement
BlockStatement
NullStatement
```

Processes:

```text
CombinationalProcess
SequentialProcess
```

Generate structures:

```text
ForGenerate
IfGenerate
```

The exact class structure may evolve if there is a clear architectural reason.

Do not make major IR changes merely to patch one generator bug.

---

# 8. RTL Type Semantics

The type system must preserve information needed for HDL translation.

Where relevant, represent:

- scalar/vector distinction
- range
- width
- signedness
- four-state capability
- index direction

The architecture must be able to distinguish semantics such as:

```text
std_logic
std_logic_vector
signed
unsigned
```

and:

```text
wire
reg
logic
signed
```

Do not discard VHDL index direction.

For example:

```text
7 downto 0
0 to 7
```

must not be treated as semantically identical merely because both have width 8.

---

# 9. Semantic Lowering

Language semantic conversion belongs in transformer/lowering stages.

Recommended responsibilities include:

```text
semantic_lowering
type_lowering
identifier_resolution
name_transformation
driver analysis when required
```

Examples:

```text
VHDL rising_edge(clk)
        ↓
canonical edge semantics
        ↓
Verilog posedge clk
```

and:

```text
SystemVerilog logic
        ↓
driver/use analysis
        ↓
Verilog wire or reg
```

Do not place these decisions inside Jinja2 templates.

Do not perform semantic conversion through textual token replacement.

---

# 10. Assignment Semantics

Correctly distinguish at least:

- VHDL signal assignment
- VHDL variable assignment
- Verilog continuous assignment
- Verilog procedural blocking assignment
- Verilog procedural non-blocking assignment

Generated Verilog should normally follow:

```text
continuous logic
→ assign

combinational procedural logic
→ blocking assignment (=)

sequential procedural logic
→ non-blocking assignment (<=)
```

Do not select assignment operators based only on source spelling.

Select them based on canonical RTL semantics.

---

# 11. Process Semantics

The architecture must distinguish combinational and sequential processes.

Typical VHDL clock patterns should be interpreted semantically.

Examples include:

```vhdl
if rising_edge(clk) then
```

and:

```vhdl
if falling_edge(clk) then
```

Sequential lowering must support common:

- positive edge clocks
- negative edge clocks
- synchronous resets
- asynchronous resets
- active-high resets
- active-low resets

Do not infer clock/reset semantics using fragile string replacement when structured AST information is available.

---

# 12. Combinational Logic Preservation

Prefer preserving a natural RTL representation.

For example:

```vhdl
y <= a when sel = '1' else b;
```

should normally become an expression-oriented Verilog construct such as:

```verilog
assign y = sel ? a : b;
```

rather than an unnecessary procedural block.

A VHDL combinational process, however, may naturally lower to:

```verilog
always @(*) begin
    ...
end
```

Do not normalize all combinational logic into one style regardless of source structure.

---

# 13. Generic / Parameter Semantics

The architecture must support:

```text
VHDL generic
↔
Verilog parameter
```

including:

- defaults
- expressions
- instance overrides

Do not flatten parameterized designs merely to simplify generation.

---

# 14. Generate Semantics

Support preservation of generate hierarchy.

Relevant concepts include:

- for-generate
- if-generate
- genvar
- Verilog generate/endgenerate

Do not unroll generate blocks into large repeated RTL unless required by semantics.

---

# 15. Identifier Handling

Use a dedicated identifier resolution layer.

It must consider:

- VHDL case-insensitive identifier rules
- Verilog/SystemVerilog case-sensitive identifiers
- target-language reserved words
- illegal identifiers
- collisions introduced during transformation
- escaped identifiers
- deterministic renaming

Default policy:

```text
preserve
```

Never automatically rename public HDL interfaces merely for style.

This includes:

- module/entity names
- ports
- instances

Optional style conversion may support:

```text
snake_case
camelCase
PascalCase
```

but only when explicitly requested.

Maintain deterministic original-name → generated-name mappings.

---

# 16. Comment Preservation

Comments are first-class source information.

Do not assume semantic AST nodes alone preserve comments.

Comment mapping may use:

- CST trivia
- token streams
- source spans
- lightweight comment scanning

A lightweight comment scanner is allowed.

A second HDL grammar parser is not.

Where practical, preserve:

- leading comments
- trailing comments
- source association

Comment preservation must not compromise RTL semantics.

---

# 17. Generator Policy

Use Jinja2 for HDL rendering.

Templates may handle:

- indentation
- whitespace
- declaration layout
- keyword rendering
- comment formatting
- line layout

Templates must not handle:

- type inference
- driver analysis
- clock inference
- reset inference
- identifier collision resolution
- wire/reg semantic decisions
- AST traversal logic that belongs in the generator

Avoid large-scale manual string concatenation for HDL generation.

Small utility strings are acceptable when not replacing the template architecture.

---

# 18. Generated Verilog Quality

Generated Verilog-2001 should be:

- syntactically valid
- deterministic
- readable
- hierarchy-preserving
- structurally close to normal RTL coding style

Avoid machine-generated names such as:

```text
_GEN_1
_GEN_2
$tmp123
$logic$xxx
```

unless a temporary is semantically necessary.

If a temporary signal is necessary, give it a deterministic and understandable name.

---

# 19. Unsupported Constructs

The MVP should reject or explicitly diagnose unsupported constructs rather than silently mistranslate them.

Examples include:

## Verification / testbench

```text
initial
assert
randomize
class
program
mailbox
```

## Unsynthesizable behavioral constructs

```text
delay
wait
file I/O
force/release
```

## Advanced VHDL types outside MVP

```text
record
access type
physical type
```

## Advanced SystemVerilog features outside MVP

```text
interface
program block
class
mailbox
dynamic array
queue
```

---

# 20. Diagnostics

Provide structured diagnostics.

Useful concepts include:

```text
Diagnostic
DiagnosticSeverity

FrontendError
UnsupportedConstructError
SemanticError
GenerationError
ValidationError
```

Diagnostics should include where available:

- error code
- message
- file
- line
- column
- source span
- source snippet
- suggestion

Unsupported syntax must never disappear silently.

---

# 21. Strict and Best-Effort Modes

Support:

```text
--strict
--best-effort
```

Strict mode:

- unsupported semantic constructs cause failure

Best-effort mode:

- safe omissions may produce warnings
- unsafe omissions must still fail

Never continue when skipping a construct would silently change hardware behavior.

---

# 22. Validators

Validation is separate from the conversion pipeline.

Conceptually support:

```text
Validator
├── SlangValidator
├── GhdlValidator
└── YosysValidator
```

Use:

- slang for Verilog/SystemVerilog validation where available
- GHDL for VHDL validation where available
- Yosys only for optional Verilog synthesis smoke testing

Never use synthesized Yosys output as the HDL-X translation IR.

---

# 23. CLI

Use Typer.

Primary target interface:

```bash
hdl-x convert input.vhd --from vhdl --to verilog -o output.v
```

Design for options such as:

```text
--from
--to
-o / --output
--strict
--best-effort
--name-style
--top
-I / --include-dir
-D / --define
--validate
--verbose
```

Also provide:

```text
hdl-x doctor
```

for environment checks.

---

# 24. Python Engineering Rules

Use:

- Python >= 3.10
- Pydantic v2
- Typer
- Jinja2
- pytest

Use a standard `src/` package layout.

Public Python APIs must have type annotations.

Code comments must be written in Chinese.

Identifiers, class names, function names, APIs, error codes, and standard HDL terminology may remain English.

Do not add comments that merely restate obvious code.

---

# 25. Subprocess Rules

Centralize external-process execution.

Avoid:

```python
shell=True
```

unless there is a documented exceptional reason.

Handle:

- Windows
- Linux
- macOS

paths safely.

Do not construct commands through unsafe shell string interpolation.

---

# 26. Testing Rules

For every implemented feature:

1. add or update tests
2. run the relevant tests
3. inspect failures
4. fix root causes
5. rerun validation

Preferred test categories:

```text
unit
integration
golden
validation
synthesis smoke
```

Generated HDL should be tested independently from parser behavior where possible.

Do not:

- delete failing tests to make progress
- weaken assertions merely to obtain green tests
- mark meaningful failures as skipped without a real environmental reason
- claim tests passed unless the command was actually executed

---

# 27. Root-Cause Rule

When a bug appears, fix it at the correct abstraction layer.

For example, if VHDL ascending ranges are lost because the canonical range model discards direction:

Bad fix:

```text
special-case the Verilog generator
```

Correct fix:

```text
repair the canonical range representation
add regression tests
verify downstream lowering/generation
```

Avoid generator-specific patches for IR design defects.

---

# 28. Dependency / API Rule

Never invent external APIs.

When using:

- slang
- pyslang
- GHDL
- pyGHDL
- libghdl
- Yosys

inspect the actual installed tool or dependency before relying on an API that might vary by version.

Prefer primary documentation or actual installed package behavior when verification is necessary.

---

# 29. Repository Safety

Before editing:

- inspect the repository
- inspect existing files
- preserve existing correct work
- avoid unrelated refactoring

Do not perform destructive Git operations.

Do not:

```text
git reset --hard
git clean -fd
force push
delete unrelated user work
```

Do not push to a remote repository unless explicitly requested.

Local checkpoint commits are optional only when the active execution plan allows them and they can be created without disturbing unrelated user changes.

---

# 30. Scope Discipline

Each task should modify only what is required for the active milestone or bug.

Do not opportunistically redesign unrelated components.

Do not implement future translation paths merely because infrastructure exists.

Prefer:

```text
small vertical slice
→ tests
→ validation
→ next slice
```

over:

```text
implement everything
→ test at the end
```

---

# 31. Unattended Execution

When the active prompt or `PLANS.md` explicitly requests unattended or continuous execution:

- continue through multiple milestones without asking for confirmation
- validate each milestone before advancing
- resolve ordinary implementation choices independently
- record important decisions
- repair regressions before continuing
- stop only for a genuine hard blocker defined by the execution plan

Do not interpret older staged-development wording as requiring user confirmation when the current execution plan explicitly enables continuous execution.

---

# 32. Definition of Good Work

A feature is not complete merely because code was written.

It is complete when:

- the architecture remains coherent
- the implementation works for its declared supported subset
- tests cover the new behavior
- relevant validation was actually run
- generated HDL is readable
- unsupported cases fail explicitly
- known limitations are documented

When uncertain, prefer conservative correctness over apparent feature coverage.