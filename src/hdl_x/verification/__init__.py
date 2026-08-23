"""HDL-X 行为验证基础设施。"""

from .equivalence import (
    DifferentialSimulationCase,
    DifferentialSimulationResult,
    IcarusCompilationCase,
    SystemVerilogDifferentialSimulationCase,
    SystemVerilogDifferentialSimulationResult,
    VerificationToolchain,
    compile_iverilog,
    detect_verification_toolchain,
    run_differential_simulation,
    run_systemverilog_differential_simulation,
)

__all__ = [
    "DifferentialSimulationCase",
    "DifferentialSimulationResult",
    "IcarusCompilationCase",
    "SystemVerilogDifferentialSimulationCase",
    "SystemVerilogDifferentialSimulationResult",
    "VerificationToolchain",
    "compile_iverilog",
    "detect_verification_toolchain",
    "run_differential_simulation",
    "run_systemverilog_differential_simulation",
]
