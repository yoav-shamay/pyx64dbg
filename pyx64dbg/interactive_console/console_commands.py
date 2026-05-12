from pyx64dbg import number_types
from typing import TYPE_CHECKING
from pyx64dbg.vector_register import VectorRegister
from pyx64dbg.stack import StackFrame

if TYPE_CHECKING:
    from pyx64dbg.interactive_console.interactive_console import InteractiveConsole

# Define all active commands once with dotted path names - single source of truth
# format - ([aliases], (["active_path"], ["inactive_path"]), "help_description" (or None for not showing)
# Paths are list of strings / lists of strings, where strings indicate attribute access and lists indicate indexing.
# Those are evaluated with the console as the root object.
ALL_COMMANDS = [
    (["run_process", "run", "r"], (["_process_already_running_trap"], ["run_process"]), "Run the process"),
    (["single_step", "step", "s"], (["debugger", "single_step"], ["_process_not_running_trap"]), "Step into the next instruction."),
    (["continue_execution", "cont", "c"], (["debugger", "continue_execution"], ["_process_not_running_trap"]), "Continue execution until the next breakpoint or the program exits."),
    (["next", "n"], (["debugger", "next"], ["_process_not_running_trap"]), "Step over to the next instruction, stepping over function calls."),
    (["finish", "fin", "f"], (["debugger", "finish"], ["_process_not_running_trap"]), "Step out of the current function."),
    (["registers", "regs"], (["debugger", "registers"], ["_process_not_running_trap"]), "View the current register values."),
    (["memory", "mem"], (["debugger", "memory"], ["_process_not_running_trap"]), "Access memory read/write"),
    (["read_number", "read_num"], (["debugger", "read_number"], ["_process_not_running_trap"]), "Read a number from memory at a given address."),
    (["write_number", "write_num"], (["debugger", "write_number"], ["_process_not_running_trap"]), "Write a number to memory at a given address."),
    (["read_c_string", "read_c_str", "read_string", "read_str"], (["debugger", "read_c_string"], ["_process_not_running_trap"]), "Read a null-terminated C string from memory at a given address."),
    (["disassemble", "dis"], (["print_disassembly"], ["_process_not_running_trap"]), "Disassemble instructions at a given address."),
    (["add_breakpoint", "brk", "b"], (["debugger", "breakpoints", "add_breakpoint"], ["_process_not_running_trap"]), "Add a breakpoint at a given address."),
    (["remove_breakpoint"], (["debugger", "breakpoints", "remove_breakpoint"], ["_process_not_running_trap"]), "Remove a breakpoint at a given address."),
    (["breakpoints", "brks", "bps"], (["print_breakpoints"], ["_process_not_running_trap"]), "View the current breakpoints."),
    (["kill"], (["debugger", "kill_process"], ["_process_not_running_trap"]), "Kill the debugged process."),
    (["surpass_signal", "surpass"], (["debugger", "surpass_signal"], ["_process_not_running_trap"]), "Surpass the current signal, allowing the process to continue execution without handling it."),
    (["debugger", "dbg"], (["debugger"], ["_process_not_running_trap"]), "Access the underlying Debugger object for more advanced operations."),
    (["stack"], (["debugger", "stack"], ["_process_not_running_trap"]), "Access the call stack and stack frames."),
    (["help"], (["help"], ["help"]), "Show this help message or get help for a specific command or object."),
    (["symbols", "syms"], (["debugger", "symbols"], ["_process_not_running_trap"]), "View the loaded symbols."),
    (["functions", "funcs"], (["debugger", "symbols", "functions"], ["_process_not_running_trap"]), "View the loaded function symbols."),
    (["objects", "objs"], (["debugger", "symbols", "objects"], ["_process_not_running_trap"]), "View the loaded object symbols."),
    (["base_address", "base_addr"], (["debugger", "base_address"], ["_process_not_running_trap"]), "View the base address of the main executable."),
    (["shared_objects"], (["debugger", "shared_objects"], ["_process_not_running_trap"]), "View the loaded shared objects."),
    (["libc"], (["debugger", "shared_objects", ["libc.so.6"]], ["_process_not_running_trap"]), "View the loaded libc shared object"),
    (["Int8", "Char"], (number_types.Int8, number_types.Int8), None),
    (["Int16", "Short"], (number_types.Int16, number_types.Int16), None),
    (["Int32", "Long"], (number_types.Int32, number_types.Int32), None),
    (["Int64"], (number_types.Int64, number_types.Int64), None),
    (["UInt8", "UChar"], (number_types.UInt8, number_types.UInt8), None),
    (["UInt16", "UShort"], (number_types.UInt16, number_types.UInt16), None),
    (["UInt32", "UInt"], (number_types.UInt32, number_types.UInt32), None),
    (["UInt64", "ULong"], (number_types.UInt64, number_types.UInt64), None),
    (["Float32", "Float"], (number_types.Float32, number_types.Float32), None),
    (["Float64", "Double"], (number_types.Float64, number_types.Float64), None),
    (["Float80", "LongDouble"], (number_types.Float80, number_types.Float80), None),
    (["select_file", "load_file", "file"], (["select_file"], ["select_file"]), "Select a file to debug."),
    (["number_types"], (number_types, number_types), None), # for help entry
    (["StackFrame"], (StackFrame, StackFrame), None), # for help entry
    (["VectorRegister"], (VectorRegister, VectorRegister), None), # for help entry
]


def _resolve_target(console: "InteractiveConsole", target_path: list):
    """
    Safely resolve a target path, created out of list of strings for dot access or lists for indexing.
    Starts from the console object.
    """
    obj = console
    for part in target_path:
        if isinstance(part, str):
            obj = getattr(obj, part)
        elif isinstance(part, list):
            # list means we need to index based on elements in the list
            for p in part:
                obj = obj[p]
    return obj


def get_available_commands(console: "InteractiveConsole", process_running: bool):
    """
    Returns a list of (aliases, target) for the commands that are available based on the process state.
    """
    res = []
    for names, (active_path, inactive_path), _ in ALL_COMMANDS:
        target = active_path if process_running else inactive_path
        if isinstance(target, list): # if the target is a list, it's a path that needs to be resolved
            try:
                target = _resolve_target(console, target)
            except:
                # if we fail to resolve the target, it means it's not available in the current state, so we assign None to it
                # this can happen for example for the 'libc' command, if libc isn't loaded in the process.
                target = None
        
        res.append((names, target))
    return res

def get_all_commands_help():
    res = []
    for names, _, help_desc in ALL_COMMANDS:
        if help_desc is not None:
            res.append((names, help_desc))
    return res

def get_all_command_names():
    """
    Get a list of all command names (aliases)
    """
    names = []
    for aliases, _, _ in ALL_COMMANDS:
        names.extend(aliases)
    return names