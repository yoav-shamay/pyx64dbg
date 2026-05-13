# PyX64Dbg
A Python-based debugger for x64 assembly in linux.
Uses the ptrace system call to control the debugged process execution.

## Features
- **Python API** - Programmatically access the debugger and all of its functionality.
- **CLI tool** - Interactive IPython-based console
- **GUI** - Graphical interface built using pyside6

## Prerequisites
- **OS**: Linux, x86-64 architecture
- **Python** - 3.10 or later
- **For building from source**:
    - C++20 compiler
    - Build tools and development headers

## Installation
### From PyPI (Recommended)
TODO, not yet published
### From Source (Development)
Installed with:
```bash
pip install -e .
```
This compiles the Pybind11 C++ extensions.

## Usage
### CLI
`pyx64dbg [/path/to/binary]`
Starts the IPython console.  
Press `help` within the console for more information on the available commands.
## GUI
`pyx64dbg-gui`
Opens the graphical interface.
## Python API
Use `pyx64dbg.Debugger` to access the debugger object.  
Example:
```python
from pyx64dbg import Debugger

# Start Debugging
dbg = debugger.start_and_debug("./binary")

# Breakpoints
# Set breakpoint and run
dbg.breakpoints.add_breakpoint(0x401000)
dbg.control.continue_execution()

# Inspect state
print(f"RIP: 0x{dbg.registers.rip:x}")
print(f"Memory at RSP: 0x{dbg.memory.read_number(dbg.registers.rsp, Int64):x}")

# Clean up
dbg.control.kill_process()
```