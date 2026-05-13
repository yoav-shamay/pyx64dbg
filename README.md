# PyX64Dbg
A Python-based debugger for x64 Linux binaries. 
It uses the `ptrace` system call to control the debugged process.
## Features
- **Python API** - Programmatically access the debugger and all of its functionality.
- **CLI tool** - Interactive IPython-based console
- **GUI** - Graphical interface built using PySide6

## Prerequisites
- **OS**: Linux, x86-64 architecture
- **Python** - 3.10 or later
- **For building from source**:
    - C++20 compiler
    - Build tools and development headers

## Installation
### From PyPI (Recommended)
Not published yet.
### From Source (Development)
Installed with:
```bash
pip install -e .
```
This compiles the Pybind11 C++ extensions.

## Usage
### CLI
```bash
pyx64dbg [/path/to/binary]
```
Starts the IPython console.  
Press `help` within the console for more information on the available commands.
## GUI
```bash
pyx64dbg-gui
```
This opens the graphical interface.
## Python API
Use `pyx64dbg.Debugger` to access the debugger object.  
Example:
```python
from pyx64dbg import Debugger
from pyx64dbg.number_types import Int64

# Start Debugging
dbg = Debugger.start_and_debug("./binary")

# Breakpoints
# Set breakpoint and run
dbg.breakpoints.add_breakpoint(0x401000)
dbg.control.continue_execution()

# Inspect state
print(f"RIP: 0x{dbg.registers.rip:x}")
print(f"Memory at RSP: 0x{dbg.memory.read_number(dbg.registers.rsp, Int64):x}")

# Clean up - kill the process to avoid leaving it hanging
dbg.control.kill_process()
```

## Limitations
- The debugger only works for Linux ELF binaries on the x86-64 architecture.
= The debugger uses the `ptrace` syscall and the `/proc` file system to gain information on the debugged process, and will not work if they aren't available.
- The GUI tool requires a desktop session (X11 or Wayland)

## Testing
Some of the tests are integration tests on specific binaries provided in the repository.  
To compile the binaries use `make` on the `test/executables` directory.  
The tests might not work on newly compiled binaries due to relying on specific address offsets.