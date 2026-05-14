# PyX64Dbg

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Linux_x86__64-lightgrey.svg)
![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**PyX64Dbg** is a Python-based debugger for x86-64 Linux binaries.

Leveraging the Linux `ptrace` API, PyX64Dbg combines low-level process control with Python's flexibility. It provides essential debugging capabilities (execution control, breakpoints, memory/register inspection) through a **Graphical User Interface (GUI)**, a robust **IPython-based CLI**, and a comprehensive **Python API** for programmatic binary analysis.

## Key Features

- **Graphical Interface:** Built with PySide6, featuring disassembly views, memory watches, register panels, and an embedded interactive terminal.
- **Advanced Target Support:** Native handling of PIE (Position Independent Executables), ASLR, shared libraries (`ld.so`), and dynamic symbols.
- **C-Like Type System:** A custom extension providing native types (`Int32`, `UInt64`, `Float80`, etc.) that strictly follow C promotion, overflow, and truncation rules.
- **Extended Registers (AVX/SSE):** Full CPU `xstate` parsing with support for interacting with `XMM`, `YMM`, and FPU (`st`) vector registers.
- **IPython REPL:** An interactive console that supports live Python syntax, auto-completion, and inline evaluation.

## Prerequisites

- **Operating System**: Linux (x86-64 architecture only)
- **Python**: 3.10 or later

## Installation

### From PyPI (Recommended)
```bash
pip install pyx64dbg
```

### From Source (Development)
Building from source compiles the underlying Pybind11 C++ extensions. 

**Additional Requirements:**
- A C++20 compatible compiler (GCC/Clang)
- Standard build tools (`make`, Python development headers)

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

PyX64Dbg is built to be scripted. You can automate binary analysis, reverse engineering, or testing using the `Debugger` object.

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

# 5. Clean up
dbg.control.kill_process()
```

## Limitations

- Supported exclusively on Linux ELF binaries running on `x86-64`.
- Relies on the `ptrace` system call and the `/proc` filesystem. It will not function in hardened environments where these features are disabled.

## Testing

The repository includes a suite of integration tests against custom-compiled C binaries to verify register states, memory reading, and edge cases.

To run the test suite:
1. Compile the test executables: `cd test/executables && make`
2. Run `pytest`: `pytest test/`

*Note: Tests rely on specific compiled offsets and may fail if rebuilt with significantly different compiler versions.*

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.