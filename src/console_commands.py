import number_types
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from interactive_console import InteractiveConsole

def get_commands(console : InteractiveConsole):
    return [
        (["single_step", "step", "s"], console.debugger.single_step, "Step into the next instruction."),
        (["continue_execution", "cont", "c"], console.debugger.continue_execution, "Continue execution until the next breakpoint or the program exits."),
        (["next", "n"], console.debugger.next, "Step over to the next instruction, stepping over function calls."),
        (["finish", "fin", "f"], console.debugger.finish, "Step out of the current function."),
        (["registers", "regs"], console.debugger.registers, "View the current register values."),
        (["memory", "mem"], console.debugger.memory, "Access memory read/write"),
        (["read_number", "read_num"], console.debugger.read_number, "Read a number from memory at a given address."),
        (["write_number", "write_num"], console.debugger.write_number, "Write a number to memory at a given address."),
        (["disassemble", "dis"], console.print_disassembly, "Disassemble instructions at a given address."),
        (["add_breakpoint", "brk", "b"], console.debugger.breakpoints.add_breakpoint, "Add a breakpoint at a given address."),
        (["remove_breakpoint"], console.debugger.breakpoints.remove_breakpoint, "Remove a breakpoint at a given address."),
        (["breakpoints", "brks", "bps"], console.print_breakpoints, "View the current breakpoints."),
        (["debugger", "dbg"], console.debugger, "Access the underlying Debugger object for more advanced operations."),
        (["stack"], console.debugger.stack, "Access the call stack and stack frames."),
        (["help"], console.help, "Show this help message or get help for a specific command or object.")
    ]

def get_number_types():
    return [("Int8", number_types.Int8),
            ("Int16", number_types.Int16),
            ("Int32", number_types.Int32),
            ("Int64", number_types.Int64),
            ("UInt8", number_types.UInt8),
            ("UInt16", number_types.UInt16),
            ("UInt32", number_types.UInt32),
            ("UInt64", number_types.UInt64),
            ("Char", number_types.Int8),
            ("Short", number_types.Int16),
            ("Int", number_types.Int32),
            ("Long", number_types.Int64),
            ("UChar", number_types.UInt8),
            ("UShort", number_types.UInt16),
            ("UInt", number_types.UInt32),
            ("ULong", number_types.UInt64)]