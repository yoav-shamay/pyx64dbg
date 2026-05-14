# PyX64Dbg

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux_x86__64-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**PyX64Dbg** is a Python-based debugger for x86-64 Linux binaries.

PyX64Dbg utilizes the Linux `ptrace` system call and the `/proc` filesystem (`procfs`) to trace and introspect ELF processes. These low-level operating system primitives are abstracted into an intuitive Python object model, enabling direct manipulation of process memory, CPU registers, and execution flow.

The tool features through three primary interfaces: a **Python API** designed for automated reverse engineering and binary analysis, a **Graphical User Interface (GUI)** for visual debugging, and a robust **IPython-based CLI** for debugging from the terminal.

## Key Features

- **Python API:** Automate reverse engineering, exploit development, or testing using a clean, object-oriented interface. Unlike GDB, PyX64Dbg acts as a standard Python library you can import and use anywhere.
- **Graphical Interface (GUI):** Built with PySide6, featuring disassembly views, memory watches, register panels, and an embedded interactive terminal.
- **Command Line Interface (CLI):** An interactive IPython REPL that supports live Python syntax, auto-completion, and inline evaluation.
- **Advanced Target Support:** Native handling of PIE (Position Independent Executables), ASLR, shared libraries (`ld.so`), and dynamic symbols.
- **C-Like Type System:** A custom extension providing native types (`Int32`, `UInt64`, `Float80`, etc.) that strictly follow C promotion, overflow, and truncation rules.
- **Extended Registers (AVX/SSE):** Supports CPU `xstate`, including `XMM`, `YMM`, and FPU (`st`) vector registers. The API allows you to seamlessly treat vector data as a C-style union across all possible integer and floating-point array representations.

## Prerequisites

- **Operating System**: Linux (x86-64 architecture only)
- **Python**: 3.10 or later
- **C++ Compiler**: A C++20 compatible compiler (e.g., `g++` or `clang`) and Python development headers are required to compile the `ptrace` and numeric type extensions during installation.

## Installation

### From PyPI (Recommended)
```bash
pip install pyx64dbg
```

### From Source (Development)
Clone the repository and install it in editable mode:
```bash
git clone https://github.com/yoav-shamay/pyx64dbg.git
cd pyx64dbg
pip install -e .
```

## Usage

### Graphical Interface (GUI)
Start the visual debugger (requires a desktop session like X11 or Wayland):
```bash
pyx64dbg-gui
```
*Tip: The full IPython CLI is embedded directly into the GUI and is available via the "Interactive Console" tab at the bottom.*

### Command Line Interface (CLI)
Launch the interactive IPython console:
```bash
pyx64dbg [/path/to/binary]
```
Once inside, simply type `help` to see a list of available commands and aliases (e.g., `run`, `step`, `bps`, `dis`).

## Python API Showcase

PyX64Dbg is built to be scripted. You can easily interact with binaries directly from Python.

```python
from pyx64dbg import Debugger
from pyx64dbg.number_types import UInt64

# 1. Spawn process and attach debugger
dbg = Debugger.start_and_debug("./target_binary")

# 2. Set a breakpoint at the 'main' function
main_addr = dbg.symbols["main"]
dbg.breakpoints.add_breakpoint(main_addr)

# 3. Run until the breakpoint is hit
dbg.control.continue_execution()

# 4. Read memory and native vector registers
rip = dbg.registers.rip
rsp_val = dbg.memory.read_number(dbg.registers.rsp, UInt64)
ymm0_floats = dbg.registers.ymm0.f32  # Access YMM0 as an array of 32-bit floats

print(f"[+] Halted at RIP: 0x{rip:x}")
print(f"[+] Stack pointer value: 0x{rsp_val:x}")
print(f"[+] YMM0 state: {ymm0_floats}")

# 5. Clean up - kill the process
dbg.control.kill_process()
```

## Limitations

- Supported exclusively on Linux ELF binaries running on `x86-64`.
- Relies on the `ptrace` system call and the `/proc` filesystem. It will not function in hardened environments where these features are disabled.

## Testing

The repository includes a suite of integration tests that run against provided pre-compiled C binaries to verify register states, memory reading, and edge cases.

To run the tests:
```bash
pytest test/
```

*Note: If you wish to rebuild the test executables from source, a `Makefile` is provided in `test/executables/`. Rebuilding may cause certain tests to fail if the compiler generates different instruction offsets.*

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.