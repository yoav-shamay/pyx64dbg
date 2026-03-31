def get_commands(console : "InteractiveConsole"):
    return [
        (["single_step", "step", "s"], console.debugger.single_step, "Step into the next instruction."),
        (["continue_execution", "cont", "c"], console.debugger.continue_execution, "Continue execution until the next breakpoint or the program exits."),
        (["next", "n"], console.debugger.next, "Step over to the next instruction, stepping over function calls."),
        (["finish", "fin", "f"], console.debugger.finish, "Step out of the current function."),
        (["registers", "regs"], console.debugger.registers, "View the current register values."),
        (["memory", "mem"], console.debugger.memory, "Access memory read/write"),
        (["read_number", "read_num"], console.debugger.memory.read_number, "Read a number from memory at a given address."),
        (["disassemble", "dis"], console.print_disassembly, "Disassemble instructions at a given address."),
        (["add_breakpoint", "brk", "b"], console.debugger.breakpoints.add_breakpoint, "Add a breakpoint at a given address."),
        (["remove_breakpoint"], console.debugger.breakpoints.remove_breakpoint, "Remove a breakpoint at a given address."),
        (["breakpoints", "brks", "bps"], console.print_breakpoints, "View the current breakpoints."),
        (["debugger", "dbg"], console.debugger, "Access the underlying Debugger object for more advanced operations."),
        (["help"], console.help, "Show this help message or get help for a specific command or object.")
    ]