import inspect
import number_types
from IPython.terminal.embed import InteractiveShellEmbed
from IPython.terminal.prompts import Prompts, Token

class ConsolePrompt(Prompts):
    def in_prompt_tokens(self, cli=None):
        return [(Token.Prompt, "PyDbg> ")]

banner = """Welcome to the PyDbg interactive console!
Type help for more information."""

help_message = """Available methods / properties:
- single_step / step / s: Step into the next instruction.
- continue_execution / cont / c: Continue execution until the next breakpoint or the program exits.
- next / n: Step over to the next instruction, stepping over function calls.
- finish / fin / f: Step out of the current function.
- registers / regs: View the current register values.
- memory / mem: Access the memory of the debugged process. Supports indexing and slicing.
- read_number / read_num: Read a number from memory at a given address.
- disassemble / dis: Disassemble instructions at a given address.
- add_breakpoint / brk / b: Add a breakpoint at a given address.
- remove_breakpoint: Remove a breakpoint at a given address.
- breakpoints / brks: View the current breakpoints.
- debugger / dbg: Access the underlying Debugger object for more advanced operations.
You can also use the number types defined in the number_types module, such as Int32, UInt64, etc., for reading numbers from memory.
Use help(object) to view the docstring for any of the above methods or properties for more details on their usage, or help(number_types) to view the available number types and their details."""

class InteractiveConsole:
    """
    An ipython-based interactive console for debugging.
    Allows the user to interact with the debugger in a REPL-like environment.
    Defines aliases for commonly used functions and attributes to make them easier to access in the interactive console.
    """
    def __init__(self, debugger):
        self.debugger = debugger
    
    def print_disassembly(self, address : int, instruction_cnt : int) -> None:
        """
        Prints the disassembly of the instructions at the given address.
        Disassembles instruction_cnt instructions.
        """
        instructions = self.debugger.memory.read_instruction(address, instruction_cnt)
        for instruction in instructions:
            print(f"0x{instruction.address:016x}: {instruction.mnemonic:<8} {instruction.op_str}")
    
    def print_breakpoints(self):
        """
        Prints the current breakpoints.
        """
        breakpoints = self.debugger.breakpoints.get_breakpoints()
        print("Current breakpoints:")
        for bp in breakpoints:
            print(f"0x{bp:016x}")
    
    def help(self, obj=None):
        """
        Show help for the given object, or general help if no object is provided.
        If the object is a function, shows its signature.
        Prints the docstring of the object if it exists.
        """
        if obj is None:
            print(help_message)
        else:
            # if a function, print its signature
            if callable(obj):
                print(f"{obj.__name__}{inspect.signature(obj)}")
            # print the docstring of the object
            docstring = obj.__doc__
            if docstring is None:
                print("No help available for this object.")
            else:
                print(docstring)

    def _get_aliases(self):
        """
        Define aliases for commonly used functions and attributes to make them easier to access in the interactive console.
        """
        return {
            "single_step": self.debugger.single_step,
            "step": self.debugger.single_step,
            "s": self.debugger.single_step,

            "continue_execution": self.debugger.continue_execution,
            "cont": self.debugger.continue_execution,
            "c": self.debugger.continue_execution,

            "next": self.debugger.next,
            "n": self.debugger.next,

            "finish": self.debugger.finish,
            "fin": self.debugger.finish,
            "f": self.debugger.finish,

            "registers": self.debugger.registers,
            "regs": self.debugger.registers,

            "memory": self.debugger.memory,
            "mem": self.debugger.memory,

            "read_number": self.debugger.memory.read_number,
            "read_num": self.debugger.memory.read_number,

            "Int8": number_types.Int8,
            "UInt8": number_types.UInt8,
            "Int16": number_types.Int16,
            "UInt16": number_types.UInt16,
            "Int32": number_types.Int32,
            "UInt32": number_types.UInt32,
            "Int64": number_types.Int64,
            "UInt64": number_types.UInt64,
            "Char": number_types.Char,
            "UChar": number_types.UChar,
            "Short": number_types.Short,
            "UShort": number_types.UShort,
            "Int": number_types.Int,
            "UInt": number_types.UInt,
            "Long": number_types.Long,
            "ULong": number_types.ULong,

            "disassemble": self.print_disassembly,
            "dis": self.print_disassembly,

            "add_breakpoint": self.debugger.breakpoints.add_breakpoint,
            "brk": self.debugger.breakpoints.add_breakpoint,
            "b": self.debugger.breakpoints.add_breakpoint,
            "remove_breakpoint": self.debugger.breakpoints.remove_breakpoint,
            "breakpoints": self.print_breakpoints,
            "brks": self.print_breakpoints,
            
            "debugger": self.debugger,
            "dbg": self.debugger,

            "help": self.help,
            "number_types": number_types,
        }
    
    def run(self):
        shell = InteractiveShellEmbed(colors='linux',user_ns=self._get_aliases() ,display_banner=False)
        shell.prompts = ConsolePrompt(shell)
        shell.autocall = 2 # automatically call functions without parentheses, e. g. "s" instead of "s()"
        print(banner)
        shell()